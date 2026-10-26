"""Train 3D Gaussians with gsplat. Intended for a CUDA host (Colab), not Apple Silicon.

This follows the original 3D Gaussian Splatting loop (Kerbl et al.) via gsplat's
DefaultStrategy: grow Gaussians where the image error is high, prune faint ones,
L1 + SSIM loss, and spherical harmonics. That is the method behind a Captures-style
walkable splat.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import numpy as np

from model.splat.colmap_txt import load_colmap_txt
from model.splat.exceptions import SplatError
from shared.config.settings import SplatSettings

_C0 = 0.28209479177387814
_SH_DEGREE = 3
_SSIM_LAMBDA = 0.2
_KEEP_EVERY = 2000


def require_cuda_gsplat() -> None:
    try:
        import torch
    except ImportError as exc:
        raise SplatError(
            "missing_dependency",
            "Splat training needs PyTorch with CUDA (install on Colab, not a second repo).",
        ) from exc
    if not torch.cuda.is_available():
        raise SplatError(
            "cuda_required",
            "Gaussian splat training needs an NVIDIA GPU. Use the Colab notebook in this repo "
            "(Runtime → GPU). Your Mac only prepares frames; it does not train the splat.",
        )
    try:
        import gsplat  # noqa: F401
    except ImportError as exc:
        raise SplatError(
            "missing_dependency",
            "Install the splat extra on the GPU machine: pip install -e '.[splat]'",
        ) from exc


def _ssim(pred, target):
    """Scalar SSIM. pred and target are [H, W, 3] in roughly 0..1."""
    import torch
    import torch.nn.functional as F

    x = pred.permute(2, 0, 1).unsqueeze(0)
    y = target.permute(2, 0, 1).unsqueeze(0)
    channel = x.shape[1]
    size = 11
    coords = torch.arange(size, device=x.device, dtype=x.dtype) - size // 2
    gauss = torch.exp(-(coords**2) / (2 * 1.5**2))
    gauss = gauss / gauss.sum()
    window = gauss.outer(gauss).expand(channel, 1, size, size).contiguous()
    pad = size // 2
    mu_x = F.conv2d(x, window, padding=pad, groups=channel)
    mu_y = F.conv2d(y, window, padding=pad, groups=channel)
    mu_x2 = mu_x * mu_x
    mu_y2 = mu_y * mu_y
    mu_xy = mu_x * mu_y
    sigma_x2 = F.conv2d(x * x, window, padding=pad, groups=channel) - mu_x2
    sigma_y2 = F.conv2d(y * y, window, padding=pad, groups=channel) - mu_y2
    sigma_xy = F.conv2d(x * y, window, padding=pad, groups=channel) - mu_xy
    c1 = 0.01**2
    c2 = 0.03**2
    value = ((2 * mu_xy + c1) * (2 * sigma_xy + c2)) / (
        (mu_x2 + mu_y2 + c1) * (sigma_x2 + sigma_y2 + c2)
    )
    return value.mean()


def _log_neighbor_scales(points):
    """Per-point log scale from an approximate nearest-neighbor distance."""
    import torch

    count = int(points.shape[0])
    ref_count = min(count, 2048)
    ref = points[torch.randperm(count, device=points.device)[:ref_count]]
    nearest = torch.empty(count, device=points.device)
    for start in range(0, count, 4096):
        chunk = points[start : start + 4096]
        dist = torch.cdist(chunk, ref)
        dist = dist.masked_fill(dist < 1e-8, 1e6)
        nearest[start : start + chunk.shape[0]] = dist.min(dim=1).values
    good = nearest < 1e5
    fallback = nearest[good].median() if bool(good.any()) else torch.tensor(0.01, device=points.device)
    nearest = torch.where(good, nearest, fallback).clamp(min=1e-4)
    # A fraction of the neighbor distance. Full distance starts as the big balloons.
    return torch.log(nearest * 0.5).unsqueeze(-1).repeat(1, 3)


def _scene_scale(frames) -> float:
    import torch

    centers = torch.stack([torch.linalg.inv(frame["viewmat"])[:3, 3] for frame in frames])
    return float((centers - centers.mean(0)).norm(dim=-1).max().clamp(min=1e-2))


def _enforce_cap(params, optimizers, state, cap: int) -> None:
    import torch
    from gsplat.strategy.ops import remove

    count = int(params["means"].shape[0])
    if count <= cap:
        return
    opacity = torch.sigmoid(params["opacities"].detach().flatten())
    _, drop = torch.topk(opacity, k=count - cap, largest=False)
    mask = torch.zeros(count, dtype=torch.bool, device=opacity.device)
    mask[drop] = True
    remove(params, optimizers, state, mask)
    print(f"capped to {int(params['means'].shape[0])} gaussians", flush=True)


def train_gsplat(
    image_dir: Path,
    colmap_txt: Path,
    output_ply: Path,
    settings: SplatSettings,
) -> Path:
    require_cuda_gsplat()
    import torch
    from gsplat import DefaultStrategy
    from gsplat.rendering import rasterization
    from PIL import Image

    model = load_colmap_txt(colmap_txt)
    cameras = model["cameras"]
    images = model["images"]
    points = model["points"]
    colors = model["colors"]
    if len(points) < 32:
        raise SplatError(
            "sparse_points",
            "COLMAP sparse cloud is too thin to seed Gaussians. Recapture with a slower orbit.",
            {"points": int(len(points))},
        )

    device = torch.device("cuda")
    cap = max(32, int(settings.max_gaussians))
    means_np = points
    rgb_np = np.clip(colors, 0.0, 1.0)
    if means_np.shape[0] > cap:
        idx = np.random.default_rng(0).choice(means_np.shape[0], size=cap, replace=False)
        means_np = means_np[idx]
        rgb_np = rgb_np[idx]

    means = torch.tensor(means_np, device=device, dtype=torch.float32)
    rgb = torch.tensor(rgb_np, device=device, dtype=torch.float32)
    scales = _log_neighbor_scales(means)
    count = int(means.shape[0])
    sh = torch.zeros((count, (_SH_DEGREE + 1) ** 2, 3), device=device)
    sh[:, 0, :] = (rgb - 0.5) / _C0
    params = torch.nn.ParameterDict(
        {
            "means": torch.nn.Parameter(means),
            "scales": torch.nn.Parameter(scales),
            "quats": torch.nn.Parameter(torch.tensor([[1.0, 0.0, 0.0, 0.0]], device=device).repeat(count, 1)),
            "opacities": torch.nn.Parameter(torch.logit(torch.full((count,), 0.1, device=device))),
            "sh0": torch.nn.Parameter(sh[:, :1, :]),
            "shN": torch.nn.Parameter(sh[:, 1:, :]),
        }
    )

    frames: list[dict] = []
    for item in images:
        jpeg = image_dir / item["name"]
        if not jpeg.is_file():
            matches = list(image_dir.glob(item["name"]))
            if not matches:
                continue
            jpeg = matches[0]
        cam = cameras[item["camera_id"]]
        image = np.asarray(Image.open(jpeg).convert("RGB"), dtype=np.float32) / 255.0
        frames.append(
            {
                "image": torch.tensor(image),
                "viewmat": torch.tensor(item["viewmat"]),
                "K": torch.tensor(cam["K"]),
                "width": image.shape[1],
                "height": image.shape[0],
            }
        )
    if len(frames) < 4:
        raise SplatError("too_few_registered", "Too few COLMAP images could be loaded for training.")

    scene_scale = _scene_scale(frames)
    steps = max(100, int(settings.train_steps))
    means_lr = 1.6e-4 * scene_scale
    spec = {
        "means": means_lr,
        "scales": 5e-3,
        "quats": 1e-3,
        "opacities": 5e-2,
        "sh0": 2.5e-3,
        "shN": 2.5e-3 / 20,
    }
    optimizers = {
        name: torch.optim.Adam([{"params": [params[name]], "lr": lr, "name": name}], eps=1e-15)
        for name, lr in spec.items()
    }
    scheduler = torch.optim.lr_scheduler.ExponentialLR(
        optimizers["means"], gamma=0.01 ** (1.0 / steps)
    )
    strategy = DefaultStrategy(
        absgrad=True,
        grow_grad2d=0.0008,
        refine_start_iter=500,
        refine_stop_iter=min(15_000, max(steps * 2 // 3, 500)),
        reset_every=3000,
        refine_every=100,
        pause_refine_after_reset=len(frames),
        verbose=True,
    )
    strategy.check_sanity(params, optimizers)
    state = strategy.initialize_state(scene_scale=scene_scale)
    print(
        f"3DGS images={len(frames)} seed={count} steps={steps} cap={cap} scene_scale={scene_scale:.3f}",
        flush=True,
    )

    for step in range(steps):
        for optimizer in optimizers.values():
            optimizer.zero_grad(set_to_none=True)
        frame = frames[step % len(frames)]
        viewmat = frame["viewmat"].to(device)
        target = frame["image"].to(device)
        sh_degree = min(step // 1000, _SH_DEGREE)
        coeffs = torch.cat([params["sh0"], params["shN"]], dim=1)
        # A random backdrop punishes see-through Gaussians, which otherwise float in the walk.
        background = torch.rand((1, 3), device=device)
        renders, _alphas, info = rasterization(
            means=params["means"],
            quats=params["quats"],
            scales=torch.exp(params["scales"]),
            opacities=torch.sigmoid(params["opacities"]),
            colors=coeffs,
            viewmats=viewmat[None],
            Ks=frame["K"].to(device)[None],
            width=frame["width"],
            height=frame["height"],
            sh_degree=sh_degree,
            packed=False,
            absgrad=True,
            rasterize_mode="classic",
            backgrounds=background,
        )
        pred = renders[0, ..., :3]
        if pred.shape[:2] != target.shape[:2]:
            pred = torch.nn.functional.interpolate(
                pred.permute(2, 0, 1)[None],
                size=target.shape[:2],
                mode="bilinear",
                align_corners=False,
            )[0].permute(1, 2, 0)
        l1 = torch.abs(pred - target).mean()
        loss = l1 * (1.0 - _SSIM_LAMBDA) + (1.0 - _ssim(pred, target)) * _SSIM_LAMBDA
        strategy.step_pre_backward(params, optimizers, state, step, info)
        loss.backward()
        strategy.step_post_backward(params, optimizers, state, step, info, packed=False)
        _enforce_cap(params, optimizers, state, cap)
        for optimizer in optimizers.values():
            optimizer.step()
        scheduler.step()
        if step % 50 == 0 or step == steps - 1:
            print(
                f"splat step {step}/{steps} gaussians={int(params['means'].shape[0])} "
                f"loss={float(loss):.4f} sh={sh_degree}",
                flush=True,
            )
        if (step + 1) % _KEEP_EVERY == 0:
            _write_snapshot(params, output_ply)
            publish_splat(output_ply)

    _write_snapshot(params, output_ply)
    publish_splat(output_ply)
    return output_ply


def _write_snapshot(params, output_ply: Path) -> None:
    import torch

    count = int(params["means"].shape[0])
    sh_rest = params["shN"].detach().permute(0, 2, 1).reshape(count, -1)
    write_gaussian_ply(
        output_ply,
        params["means"].detach().cpu().numpy(),
        params["sh0"].detach()[:, 0, :].cpu().numpy(),
        torch.exp(params["scales"]).detach().cpu().numpy(),
        torch.nn.functional.normalize(params["quats"].detach(), dim=-1).cpu().numpy(),
        torch.sigmoid(params["opacities"].detach()).cpu().numpy(),
        sh_rest=sh_rest.cpu().numpy(),
    )


def publish_splat(path: Path, keep_dir: str | None = None) -> Path | None:
    """Copy a PLY to keep_dir/point_cloud.ply. A mid-write disconnect leaves the previous file."""
    destination_root = keep_dir if keep_dir is not None else os.environ.get("SPLAT_KEEP_DIR", "").strip()
    if not destination_root:
        return None
    dest = Path(destination_root) / "point_cloud.ply"
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        temporary = dest.with_name("point_cloud.ply.tmp")
        shutil.copy2(path, temporary)
        os.replace(temporary, dest)
    except OSError as exc:
        print(f"keep failed: {exc}", flush=True)
        return None
    print(f"kept {dest} bytes={dest.stat().st_size}", flush=True)
    return dest


def write_gaussian_ply(
    path: Path,
    means: np.ndarray,
    sh_dc: np.ndarray,
    scales: np.ndarray,
    quats: np.ndarray,
    opacities: np.ndarray,
    sh_rest: np.ndarray | None = None,
) -> None:
    """Write a 3DGS-style PLY that splat web viewers can load."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    count = int(len(means))
    fields = [
        ("x", "<f4"),
        ("y", "<f4"),
        ("z", "<f4"),
        ("nx", "<f4"),
        ("ny", "<f4"),
        ("nz", "<f4"),
        ("f_dc_0", "<f4"),
        ("f_dc_1", "<f4"),
        ("f_dc_2", "<f4"),
    ]
    rest = None
    if sh_rest is not None:
        rest = np.asarray(sh_rest, dtype=np.float32)
        if rest.ndim != 2 or rest.shape[0] != count:
            raise ValueError("sh_rest must have one row per Gaussian")
        fields.extend((f"f_rest_{i}", "<f4") for i in range(rest.shape[1]))
    fields.extend(
        [
            ("opacity", "<f4"),
            ("scale_0", "<f4"),
            ("scale_1", "<f4"),
            ("scale_2", "<f4"),
            ("rot_0", "<f4"),
            ("rot_1", "<f4"),
            ("rot_2", "<f4"),
            ("rot_3", "<f4"),
        ]
    )
    vertices = np.empty(count, dtype=np.dtype(fields))
    vertices["x"] = means[:, 0]
    vertices["y"] = means[:, 1]
    vertices["z"] = means[:, 2]
    vertices["nx"] = 0
    vertices["ny"] = 0
    vertices["nz"] = 0
    vertices["f_dc_0"] = sh_dc[:, 0]
    vertices["f_dc_1"] = sh_dc[:, 1]
    vertices["f_dc_2"] = sh_dc[:, 2]
    if rest is not None:
        for i in range(rest.shape[1]):
            vertices[f"f_rest_{i}"] = rest[:, i]
    inv_s = np.clip(opacities, 1e-4, 1 - 1e-4)
    vertices["opacity"] = np.log(inv_s / (1.0 - inv_s))
    log_scale = np.log(np.clip(scales, 1e-6, None))
    vertices["scale_0"] = log_scale[:, 0]
    vertices["scale_1"] = log_scale[:, 1]
    vertices["scale_2"] = log_scale[:, 2]
    vertices["rot_0"] = quats[:, 0]
    vertices["rot_1"] = quats[:, 1]
    vertices["rot_2"] = quats[:, 2]
    vertices["rot_3"] = quats[:, 3]
    names = "\n".join(f"property float {name}" for name, _ in fields)
    header = (
        "ply\n"
        "format binary_little_endian 1.0\n"
        f"element vertex {count}\n"
        f"{names}\n"
        "end_header\n"
    )
    with path.open("wb") as handle:
        handle.write(header.encode("ascii"))
        vertices.tofile(handle)
