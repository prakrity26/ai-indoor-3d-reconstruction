"""Gaussian splat reconstruction (Captures-like look). Same repository; GPU on Colab."""

from model.splat.exceptions import SplatError
from model.splat.pipeline import reconstruct_gaussian_splat
from model.splat.prepare import prepare_splat_images

__all__ = ["SplatError", "reconstruct_gaussian_splat", "prepare_splat_images"]
