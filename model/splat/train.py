"""Train 3D Gaussians with gsplat. Intended for a CUDA host (Colab), not Apple Silicon."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from model.splat.colmap_txt import load_colmap_txt
from model.splat.exceptions import SplatError
from shared.config.settings import SplatSettings


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


def train_gsplat(
    image_dir: Path,
    colmap_txt: Path,
    output_ply: Path,
    settings: SplatSettings,
) -> Path:
    require_cuda_gsplat()
    import torch
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
    means = torch.tensor(points, device=device, dtype=torch.float32)
    rgb = torch.nn.Parameter(torch.tensor(colors, device=device, dtype=torch.float32).clamp(0, 1))
    if means.shape[0] > 200_000:
        idx = torch.randperm(means.shape[0], device=device)[:200_000]
        means = means[idx]
        rgb = torch.nn.Parameter(rgb.detach()[idx])

    scales = torch.nn.Parameter(torch.full((means.shape[0], 3), np.log(0.02), device=device))
    quats = torch.zeros((means.shape[0], 4), device=device)
    quats[:, 0] = 1.0
    quats = torch.nn.Parameter(quats)
    opacities = torch.nn.Parameter(torch.logit(torch.full((means.shape[0],), 0.1, device=device)))
    means = torch.nn.Parameter(means)
    optimizer = torch.optim.Adam(
        [
            {"params": [means], "lr": 0.00016},
            {"params": [scales], "lr": 0.005},
            {"params": [quats], "lr": 0.001},
            {"params": [opacities], "lr": 0.05},
            {"params": [rgb], "lr": 0.0025},
        ]
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
                "image": torch.tensor(image, device=device),
                "viewmat": torch.tensor(item["viewmat"], device=device),
                "K": torch.tensor(cam["K"], device=device),
                "width": image.shape[1],
                "height": image.shape[0],
            }
        )
    if len(frames) < 4:
        raise SplatError("too_few_registered", "Too few COLMAP images could be loaded for training.")

    steps = max(100, int(settings.train_steps))
    for step in range(steps):
        frame = frames[step % len(frames)]
        optimizer.zero_grad(set_to_none=True)
        renders, _alphas, _meta = rasterization(
            means=means,
            quats=torch.nn.functional.normalize(quats, dim=-1),
            scales=torch.exp(scales),
            opacities=torch.sigmoid(opacities),
            colors=rgb.clamp(0, 1),
            viewmats=frame["viewmat"][None],
            Ks=frame["K"][None],
            width=frame["width"],
            height=frame["height"],
            packed=False,
            sh_degree=0,
        )
        pred = renders[0]
        target = frame["image"]
        if pred.shape[:2] != target.shape[:2]:
            pred = torch.nn.functional.interpolate(
                pred.permute(2, 0, 1)[None],
                size=target.shape[:2],
                mode="bilinear",
                align_corners=False,
            )[0].permute(1, 2, 0)
        loss = torch.abs(pred - target).mean()
        loss.backward()
        optimizer.step()

    sh_dc = ((rgb.detach().clamp(0, 1) - 0.5) / 0.28209479177387814).cpu().numpy()
    write_gaussian_ply(
        output_ply,
        means.detach().cpu().numpy(),
        sh_dc,
        torch.exp(scales).detach().cpu().numpy(),
        torch.nn.functional.normalize(quats, dim=-1).detach().cpu().numpy(),
        torch.sigmoid(opacities).detach().cpu().numpy(),
    )
    return output_ply


def write_gaussian_ply(
    path: Path,
    means: np.ndarray,
    sh_dc: np.ndarray,
    scales: np.ndarray,
    quats: np.ndarray,
    opacities: np.ndarray,
) -> None:
    """Write a 3DGS-style PLY that splat web viewers can load."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    count = int(len(means))
    dtype = np.dtype(
        [
            ("x", "<f4"),
            ("y", "<f4"),
            ("z", "<f4"),
            ("nx", "<f4"),
            ("ny", "<f4"),
            ("nz", "<f4"),
            ("f_dc_0", "<f4"),
            ("f_dc_1", "<f4"),
            ("f_dc_2", "<f4"),
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
    vertices = np.empty(count, dtype=dtype)
    vertices["x"] = means[:, 0]
    vertices["y"] = means[:, 1]
    vertices["z"] = means[:, 2]
    vertices["nx"] = 0
    vertices["ny"] = 0
    vertices["nz"] = 0
    vertices["f_dc_0"] = sh_dc[:, 0]
    vertices["f_dc_1"] = sh_dc[:, 1]
    vertices["f_dc_2"] = sh_dc[:, 2]
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
    header = (
        "ply\n"
        "format binary_little_endian 1.0\n"
        f"element vertex {count}\n"
        "property float x\nproperty float y\nproperty float z\n"
        "property float nx\nproperty float ny\nproperty float nz\n"
        "property float f_dc_0\nproperty float f_dc_1\nproperty float f_dc_2\n"
        "property float opacity\n"
        "property float scale_0\nproperty float scale_1\nproperty float scale_2\n"
        "property float rot_0\nproperty float rot_1\nproperty float rot_2\nproperty float rot_3\n"
        "end_header\n"
    )
    with path.open("wb") as handle:
        handle.write(header.encode("ascii"))
        vertices.tofile(handle)
