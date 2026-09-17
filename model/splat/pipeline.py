"""Gaussian splat path: video → COLMAP → gsplat. Same repo; GPU is Colab or a CUDA worker."""

from __future__ import annotations

from pathlib import Path
from shutil import copy2

from model.splat.colmap import run_colmap
from model.splat.exceptions import SplatError
from model.splat.prepare import prepare_splat_images
from model.splat.train import train_gsplat
from model.splat.types import (
    STRATEGY_NAME,
    SplatIssue,
    SplatResult,
    dump_splat_manifest,
)
from shared.config.settings import SplatSettings, load_splat_settings


def reconstruct_gaussian_splat(
    source: str | Path,
    *,
    job_id: str | None = None,
    frames_dir: str | Path | None = None,
    prepare_only: bool = False,
    settings: SplatSettings | None = None,
) -> SplatResult:
    """Build a walkable splat. Run training on CUDA (Colab). Mac can ``prepare_only``."""
    settings = settings or load_splat_settings()
    try:
        settings.validate()
    except ValueError as exc:
        raise SplatError("invalid_settings", str(exc)) from exc

    path = Path(source)
    warnings: list[SplatIssue] = [
        SplatIssue(
            "info",
            "same_repo",
            "Splat training lives in this repository under model/splat. Colab only supplies a GPU.",
        )
    ]

    if path.is_dir() and (path / "splat" / "images").is_dir():
        job = job_id or path.name
        job_dir = path.resolve()
        image_dir = job_dir / "splat" / "images"
        image_count = len(list(image_dir.glob("*.jpg"))) + len(list(image_dir.glob("*.png")))
    else:
        job, image_dir, image_count = prepare_splat_images(
            path,
            job_id=job_id,
            frames_dir=frames_dir,
            settings=settings,
        )
        job_dir = image_dir.parent.parent

    ply_path = ""
    colmap_dir = ""
    registered = 0
    if prepare_only:
        warnings.append(
            SplatIssue(
                "info",
                "prepare_only",
                "Frames are ready. Open notebooks/colab_gaussian_splat.ipynb on a GPU runtime to train.",
            )
        )
    else:
        colmap_txt = run_colmap(image_dir, job_dir / "splat" / "colmap", binary=settings.colmap_bin)
        colmap_dir = str(colmap_txt.resolve())
        from model.splat.colmap_txt import load_colmap_txt

        registered = len(load_colmap_txt(colmap_txt)["images"])
        ply = job_dir / "splat" / "point_cloud.ply"
        train_gsplat(image_dir, colmap_txt, ply, settings)
        ply_path = str(ply.resolve())
        extra = settings.output_dir / job / "point_cloud.ply"
        extra.parent.mkdir(parents=True, exist_ok=True)
        if extra.resolve() != ply.resolve():
            copy2(ply, extra)

    result = SplatResult(
        job_id=job,
        strategy=STRATEGY_NAME,
        image_count=image_count,
        registered_images=registered,
        ply_path=ply_path,
        colmap_dir=colmap_dir,
        manifest_path=str((job_dir / "splat" / "splat.json").resolve()),
        warnings=warnings,
    )
    dump_splat_manifest(result, job_dir / "splat" / "splat.json")
    return result
