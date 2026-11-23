"""Gaussian splat training with Nerfstudio splatfacto (the default GPU-worker backend).

The in-repo gsplat loop (``model.splat.train``) produced sparse ~1 MB clouds on phone video;
splatfacto is the standard phone-video recipe and is what the IMG_7916 notebook moved to.

    ffmpeg                 → ~180 evenly spaced frames, long side ≤ SPLAT_MAX_SIDE (1600)
    ns-process-data images → COLMAP poses
    ns-train splatfacto    → 3D Gaussians (progress parsed from its step table)
    ns-export gaussian-splat → splat.ply (3DGS layout, loads in the web viewer)

Shrinking frames before COLMAP matters on Colab: its COLMAP runs on the CPU, and full-size
4K phone frames made feature extraction alone take ~27 minutes. Training already uses
downscaled images, so 1600 px loses nothing visible.

With ``persist_dir`` (the worker uses Google Drive on Colab), the COLMAP result and training
checkpoints are kept there. A worker that reconnects after a Colab disconnect skips COLMAP and
continues training from the last checkpoint instead of starting over.

Needs a CUDA machine with ``pip install nerfstudio`` and ``apt-get install colmap ffmpeg``.
"""

from __future__ import annotations

import contextlib
import glob
import json
import os
import re
import shutil
import signal
import subprocess
import threading
from collections import deque
from collections.abc import Callable
from pathlib import Path

from model.splat.exceptions import SplatError

Report = Callable[[str, int], None]

# ns-train prints rows such as "  1200 (4.00%)   45.1 ms   21 m, 3 s ...".
_STEP_ROW = re.compile(r"^\s*(\d+)\s+\(\s*(\d+(?:\.\d+)?)%\)")

# Share of the overall progress bar given to each step.
_PROCESS = (2, 15)
_TRAIN = (15, 95)
_EXPORT = (95, 99)


def require_nerfstudio() -> None:
    tools = ("ns-process-data", "ns-train", "ns-export", "colmap", "ffmpeg", "ffprobe")
    missing = [tool for tool in tools if shutil.which(tool) is None]
    if missing:
        raise SplatError(
            "missing_dependency",
            f"Missing on this GPU machine: {', '.join(missing)}. "
            "Install with: apt-get install -y colmap ffmpeg && pip install nerfstudio",
            {"missing": missing},
        )


def train_splatfacto(
    video: str | Path,
    work_dir: str | Path,
    *,
    report: Report | None = None,
    cancel: threading.Event | None = None,
    frames: int | None = None,
    steps: int | None = None,
    min_bytes: int | None = None,
    max_side: int | None = None,
    persist_dir: str | Path | None = None,
) -> Path:
    """Train a splat from ``video``. Returns the exported PLY path."""
    require_nerfstudio()
    report = report or (lambda stage, progress: None)
    cancel = cancel or threading.Event()
    frames = frames or int(os.environ.get("SPLAT_NUM_FRAMES", "180"))
    steps = steps or int(os.environ.get("SPLAT_TRAIN_STEPS", "30000"))
    min_bytes = min_bytes if min_bytes is not None else int(os.environ.get("SPLAT_MIN_BYTES", "5000000"))
    max_side = max_side or int(os.environ.get("SPLAT_MAX_SIDE", "1600"))

    work = Path(work_dir)
    data = work / "ns_data"
    export = work / "ns_export"
    for folder in (data, export, work / "frames"):
        shutil.rmtree(folder, ignore_errors=True)
    persist = Path(persist_dir) if persist_dir else None
    outputs = (persist / "ns_outputs") if persist else (work / "ns_outputs")
    if not persist:
        shutil.rmtree(outputs, ignore_errors=True)
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}
    # gsplat compiles its CUDA kernels on first use. Unlimited parallel nvcc jobs ran Colab out of
    # memory (exit 137, "Killed"); two at a time fits in ~12 GB of RAM.
    env.setdefault("MAX_JOBS", "2")
    # PyTorch ≥ 2.6 loads checkpoints with weights_only=True, and Nerfstudio's checkpoints hold
    # numpy scalars, so ns-export failed with "Weights only load failed" after a full training
    # run. These are checkpoints this worker just wrote, so the full loader is safe here.
    env.setdefault("TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD", "1")
    _limit_colmap_threads(work, env)

    # ---- camera poses (or restore them) -------------------------------------------------------
    fingerprint = {"video_bytes": Path(video).stat().st_size, "frames": frames, "max_side": max_side}
    if persist and _can_resume(persist, fingerprint):
        report("Restoring camera poses from Drive", _PROCESS[0])
        shutil.copytree(persist / "ns_data", data)
        print(f"resumed: camera poses from {persist / 'ns_data'}", flush=True)
    else:
        if persist:
            shutil.rmtree(persist, ignore_errors=True)  # different video or settings: start clean
            persist.mkdir(parents=True, exist_ok=True)
        report("Extracting frames", _PROCESS[0])
        frame_dir = work / "frames"
        _extract_frames(Path(video), frame_dir, frames, max_side, env=env, cancel=cancel)
        report("Estimating camera poses (COLMAP)", _PROCESS[0] + 1)
        _run(
            [
                "ns-process-data", "images",
                "--data", str(frame_dir),
                "--output-dir", str(data),
                "--matching-method", "sequential",
                # Colab's apt COLMAP has no CUDA build.
                "--no-gpu",
            ],
            env=env,
            cancel=cancel,
            stage="Estimating camera poses (COLMAP)",
        )
        _use_largest_model(data, frame_dir, env=env, cancel=cancel)
        shutil.rmtree(frame_dir, ignore_errors=True)
        if persist:
            report("Saving camera poses to Drive", _PROCESS[1] - 1)
            shutil.copytree(data, persist / "ns_data", ignore=shutil.ignore_patterns("database.db"))
            (persist / "fingerprint.json").write_text(json.dumps(fingerprint))
    registered, sampled = _registration(data, frames)
    report(f"Poses ready ({registered} of {sampled} frames)", _PROCESS[1])
    min_ratio = float(os.environ.get("SPLAT_MIN_REGISTERED", "0.3"))
    if sampled and registered < max(8, int(sampled * min_ratio)):
        raise SplatError(
            "camera_poses_failed",
            f"COLMAP could place only {registered} of {sampled} frames in 3D, too few to train a splat. "
            "This usually means fast motion or blur, blank walls, or too little overlap between views. "
            "Film again more slowly, overlapping your path, with good light (see the capture tips).",
            {"registered": registered, "sampled": sampled},
        )

    # ---- training (resuming from the last checkpoint when there is one) -----------------------
    def on_line(line: str) -> None:
        match = _STEP_ROW.match(line)
        if match:
            done = float(match.group(2))
            low, high = _TRAIN
            report(f"Training Gaussians · step {match.group(1)}/{steps}", int(low + (high - low) * done / 100))

    command = [
        "ns-train", "splatfacto",
        "--data", str(data),
        "--output-dir", str(outputs),
        "--max-num-iterations", str(steps),
        "--viewer.quit-on-train-completion", "True",
    ]
    checkpoints = latest_checkpoint_dir(outputs)
    if checkpoints is not None:
        command += ["--load-dir", str(checkpoints)]
        report("Resuming training from the last checkpoint", _TRAIN[0])
        print(f"resumed: training from {checkpoints}", flush=True)
    _run(command, env=env, cancel=cancel, stage="Training Gaussians", on_line=on_line)

    configs = sorted(glob.glob(str(outputs / "**" / "config.yml"), recursive=True), key=os.path.getmtime)
    if not configs:
        raise SplatError("no_config", "Training finished without writing a config.yml.")
    report("Exporting splat", _EXPORT[0])
    _run(
        ["ns-export", "gaussian-splat", "--load-config", configs[-1], "--output-dir", str(export)],
        env=env,
        cancel=cancel,
        stage="Exporting splat",
    )
    plys = glob.glob(str(export / "**" / "*.ply"), recursive=True)
    if not plys:
        raise SplatError("no_export", "ns-export wrote no PLY file.")
    ply = Path(max(plys, key=os.path.getsize))
    size = ply.stat().st_size
    if size < min_bytes:
        raise SplatError(
            "sparse_splat",
            f"The exported splat is only {size / 1e6:.1f} MB, which means most frames did not register. "
            "Film a slower walk with more overlap and train again.",
            {"bytes": size, "frames": registered},
        )
    report("Uploading splat", _EXPORT[1])
    return ply


def colmap_models(data: Path) -> dict[str, int]:
    """Registered-image count of every model COLMAP wrote under ``data/colmap/sparse``.

    When the mapper cannot connect all frames it writes several models (0, 1, 2, …) and their
    order says nothing about size. A real IMG_1299 run gave 4, 88 and 216 frames.
    """
    models: dict[str, int] = {}
    root = data / "colmap" / "sparse"
    if not root.is_dir():
        return models
    for folder in sorted(root.iterdir()):
        images = folder / "images.bin"
        if images.is_file() and images.stat().st_size >= 8:
            with images.open("rb") as handle:
                models[folder.name] = int.from_bytes(handle.read(8), "little")
    return models


def _use_largest_model(data: Path, frame_dir: Path, *, env: dict, cancel: threading.Event) -> None:
    """ns-process-data always converts sparse/0. Rebuild transforms.json from the biggest model."""
    models = colmap_models(data)
    if len(models) < 2:
        return
    best = max(models, key=models.get)
    print(f"COLMAP models (frames placed): {models}; using sparse/{best}", flush=True)
    if best == "0" or models[best] <= models.get("0", 0):
        return
    _run(
        [
            "ns-process-data", "images",
            "--data", str(frame_dir),
            "--output-dir", str(data),
            "--skip-colmap",
            "--colmap-model-path", f"colmap/sparse/{best}",
        ],
        env=env,
        cancel=cancel,
        stage="Estimating camera poses (COLMAP)",
    )


def colmap_threads() -> int:
    """Threads COLMAP may use: SPLAT_COLMAP_THREADS, else the CPUs this process may run on (≤ 16).

    COLMAP's default is one thread per *host* core. On rented GPU pods the container sees all 96+
    cores of the machine but only ~35 GB of RAM, and CPU SIFT extraction then gets OOM-killed.
    """
    configured = os.environ.get("SPLAT_COLMAP_THREADS", "").strip()
    if configured:
        return max(1, int(configured))
    try:
        available = len(os.sched_getaffinity(0))
    except (AttributeError, OSError):
        available = os.cpu_count() or 4
    quota = _cgroup_cpus()
    if quota:
        available = min(available, quota)
    return max(1, min(16, available))


def _cgroup_cpus() -> int | None:
    try:
        quota, period = Path("/sys/fs/cgroup/cpu.max").read_text().split()[:2]
        if quota != "max":
            return max(1, int(int(quota) / int(period)))
    except (OSError, ValueError):
        pass
    return None


def _limit_colmap_threads(work: Path, env: dict) -> None:
    """Put a ``colmap`` shim first on PATH that caps its thread count (ns-process-data has no flag)."""
    real = shutil.which("colmap", path=env.get("PATH"))
    if real is None:
        return
    threads = colmap_threads()
    bin_dir = work / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    shim = bin_dir / "colmap"
    shim.write_text(
        "#!/bin/sh\n"
        f'real="{real}"\n'
        'sub="$1"; [ $# -gt 0 ] && shift\n'
        'case "$sub" in\n'
        f'  feature_extractor) exec "$real" "$sub" --SiftExtraction.num_threads {threads} "$@" ;;\n'
        f'  *_matcher) exec "$real" "$sub" --SiftMatching.num_threads {threads} "$@" ;;\n'
        f'  mapper) exec "$real" "$sub" --Mapper.num_threads {threads} "$@" ;;\n'
        '  *) exec "$real" "$sub" "$@" ;;\n'
        "esac\n"
    )
    shim.chmod(0o755)
    env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"


def _registration(data: Path, sampled_target: int) -> tuple[int, int]:
    """(frames COLMAP posed, frames that were sampled). transforms.json lists only posed frames."""
    try:
        posed = len(json.loads((data / "transforms.json").read_text()).get("frames") or [])
    except (OSError, ValueError):
        posed = 0
    images = data / "images"
    sampled = len([p for p in images.iterdir() if p.is_file()]) if images.is_dir() else 0
    return posed, max(sampled, posed) or sampled_target


def latest_checkpoint_dir(outputs: Path) -> Path | None:
    """The nerfstudio_models folder holding the newest step-*.ckpt under ``outputs``, if any."""
    found = glob.glob(str(Path(outputs) / "**" / "nerfstudio_models" / "step-*.ckpt"), recursive=True)
    if not found:
        return None
    return Path(max(found, key=_checkpoint_step)).parent


def _checkpoint_step(path: str) -> int:
    match = re.search(r"step-(\d+)\.ckpt$", path)
    return int(match.group(1)) if match else -1


def _can_resume(persist: Path, fingerprint: dict) -> bool:
    try:
        saved = json.loads((persist / "fingerprint.json").read_text())
    except (OSError, ValueError):
        return False
    return saved == fingerprint and (persist / "ns_data" / "transforms.json").is_file()


def _extract_frames(video: Path, out: Path, count: int, max_side: int, *, env: dict, cancel: threading.Event) -> None:
    """``count`` evenly spaced JPEGs, long side at most ``max_side`` (never upscaled)."""
    out.mkdir(parents=True, exist_ok=True)
    duration = _duration_seconds(video, env)
    rate = max(0.05, count / duration) if duration > 0 else 2.0
    scale = f"scale='min({max_side},iw)':'min({max_side},ih)':force_original_aspect_ratio=decrease"
    _run(
        [
            "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
            "-i", str(video),
            "-vf", f"fps={rate:.5f},{scale}",
            "-q:v", "2",
            str(out / "frame_%05d.jpg"),
        ],
        env=env,
        cancel=cancel,
        stage="Extracting frames",
    )
    extracted = len(list(out.glob("*.jpg")))
    print(f"extracted {extracted} frames (long side ≤ {max_side}px)", flush=True)
    if extracted < 8:
        raise SplatError("too_few_frames", f"Only {extracted} frames could be read from the video.")


def _duration_seconds(video: Path, env: dict) -> float:
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)],
            capture_output=True, text=True, env=env, timeout=60,
        )
        return float(result.stdout.strip())
    except (ValueError, subprocess.SubprocessError, OSError):
        return 0.0


def _run(
    command: list[str],
    *,
    env: dict[str, str],
    cancel: threading.Event,
    stage: str,
    on_line: Callable[[str], None] | None = None,
) -> None:
    """Run a command, echo its output (so Colab shows it), parse lines, honour cancel."""
    print("+", " ".join(command), flush=True)
    tail: deque[str] = deque(maxlen=30)
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env=env,
        # Own process group, so cancelling also stops children (COLMAP, dataloader workers)
        # that would otherwise keep the output pipe open.
        start_new_session=True,
    )
    watcher = threading.Thread(target=_kill_on_cancel, args=(process, cancel), daemon=True)
    watcher.start()
    assert process.stdout is not None
    for line in process.stdout:
        print(line, end="", flush=True)
        tail.append(line.rstrip())
        if on_line is not None:
            on_line(line)
    code = process.wait()
    if cancel.is_set():
        raise SplatError("cancelled", "The server cancelled this job.")
    if code != 0:
        detail = "\n".join(line for line in tail if line)[-1500:]
        raise SplatError("command_failed", f"{stage} failed (exit {code}).\n{detail}", {"command": command[0]})


def _kill_on_cancel(process: subprocess.Popen, cancel: threading.Event) -> None:
    while process.poll() is None:
        if cancel.wait(1.0):
            _signal_group(process, signal.SIGTERM)
            try:
                process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                _signal_group(process, signal.SIGKILL)
            return


def _signal_group(process: subprocess.Popen, sig: int) -> None:
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(os.getpgid(process.pid), sig)
