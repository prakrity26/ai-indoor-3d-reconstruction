"""Gaussian splat training with Nerfstudio splatfacto (the default GPU-worker backend).

The in-repo gsplat loop (``model.splat.train``) produced sparse ~1 MB clouds on phone video;
splatfacto is the standard phone-video recipe and is what the IMG_7916 notebook moved to.

    ns-process-data video  → COLMAP poses + downscaled frames
    ns-train splatfacto    → 3D Gaussians (progress parsed from its step table)
    ns-export gaussian-splat → splat.ply (3DGS layout, loads in the web viewer)

Needs a CUDA machine with ``pip install nerfstudio`` and ``apt-get install colmap ffmpeg``.
"""

from __future__ import annotations

import glob
import os
import re
import shutil
import signal
import subprocess
import threading
from collections import deque
from pathlib import Path
from typing import Callable

from model.splat.exceptions import SplatError

Report = Callable[[str, int], None]

# ns-train prints rows such as "  1200 (4.00%)   45.1 ms   21 m, 3 s ...".
_STEP_ROW = re.compile(r"^\s*(\d+)\s+\(\s*(\d+(?:\.\d+)?)%\)")

# Share of the overall progress bar given to each step.
_PROCESS = (2, 15)
_TRAIN = (15, 95)
_EXPORT = (95, 99)


def require_nerfstudio() -> None:
    missing = [tool for tool in ("ns-process-data", "ns-train", "ns-export", "colmap", "ffmpeg") if shutil.which(tool) is None]
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
) -> Path:
    """Train a splat from ``video``. Returns the exported PLY path."""
    require_nerfstudio()
    report = report or (lambda stage, progress: None)
    cancel = cancel or threading.Event()
    frames = frames or int(os.environ.get("SPLAT_NUM_FRAMES", "180"))
    steps = steps or int(os.environ.get("SPLAT_TRAIN_STEPS", "30000"))
    min_bytes = min_bytes if min_bytes is not None else int(os.environ.get("SPLAT_MIN_BYTES", "5000000"))

    work = Path(work_dir)
    data = work / "ns_data"
    outputs = work / "ns_outputs"
    export = work / "ns_export"
    for folder in (data, outputs, export):
        shutil.rmtree(folder, ignore_errors=True)
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}

    report("Estimating camera poses (COLMAP)", _PROCESS[0])
    _run(
        [
            "ns-process-data", "video",
            "--data", str(video),
            "--output-dir", str(data),
            "--num-frames-target", str(frames),
            "--matching-method", "sequential",
            # Colab's apt COLMAP has no CUDA build.
            "--no-gpu",
        ],
        env=env,
        cancel=cancel,
        stage="Estimating camera poses (COLMAP)",
    )
    registered = len(list((data / "images").glob("*"))) if (data / "images").is_dir() else 0
    report(f"Poses ready ({registered} frames)", _PROCESS[1])

    def on_line(line: str) -> None:
        match = _STEP_ROW.match(line)
        if match:
            done = float(match.group(2))
            low, high = _TRAIN
            report(f"Training Gaussians · step {match.group(1)}/{steps}", int(low + (high - low) * done / 100))

    _run(
        [
            "ns-train", "splatfacto",
            "--data", str(data),
            "--output-dir", str(outputs),
            "--max-num-iterations", str(steps),
            "--viewer.quit-on-train-completion", "True",
        ],
        env=env,
        cancel=cancel,
        stage="Training Gaussians",
        on_line=on_line,
    )

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
    try:
        os.killpg(os.getpgid(process.pid), sig)
    except (ProcessLookupError, PermissionError):
        pass
