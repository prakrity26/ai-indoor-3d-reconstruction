"""Depth Anything V2 Small via transformers. Weights only; no Hugging Face videos."""

from __future__ import annotations

import numpy as np

from model.depth.exceptions import DepthEstimationError


def _import_torch_stack():
    """Import torch/transformers without our `queue/` package shadowing stdlib."""
    from model.depth.device import ensure_stdlib_queue

    ensure_stdlib_queue()
    import torch
    from PIL import Image
    from transformers import AutoImageProcessor, AutoModelForDepthEstimation

    return torch, Image, AutoImageProcessor, AutoModelForDepthEstimation


class DepthAnythingV2Estimator:
    name = "depth_anything_v2_small"

    def __init__(
        self,
        model_id: str,
        device: str,
        *,
        local_files_only: bool = False,
        max_size: int = 768,
    ) -> None:
        try:
            torch, Image, AutoImageProcessor, AutoModelForDepthEstimation = _import_torch_stack()
        except ImportError as exc:
            raise DepthEstimationError(
                "missing_dependency",
                "Depth Anything V2 needs the optional depth extra: pip install -e '.[depth]'",
                {"import_error": str(exc)},
            ) from exc

        self._torch = torch
        self._Image = Image
        self.device = device
        self.model_id = model_id
        self.max_size = max_size
        try:
            self.processor = AutoImageProcessor.from_pretrained(
                model_id,
                local_files_only=local_files_only,
            )
            self.model = AutoModelForDepthEstimation.from_pretrained(
                model_id,
                local_files_only=local_files_only,
            )
        except OSError as exc:
            raise DepthEstimationError(
                "weights_unavailable",
                (
                    "Could not load Depth Anything V2 weights. This stage needs the "
                    "model checkpoint, not a Hugging Face demo video. Place your own "
                    "indoor video under data/uploads and allow a one-time weight download, "
                    "or set DEPTH_LOCAL_FILES_ONLY=1 after caching the model."
                ),
                {"model_id": model_id, "error": str(exc)},
            ) from exc

        try:
            self.model.to(device)
        except Exception:
            self.device = "cpu"
            self.model.to("cpu")
        self.model.eval()

    def infer(self, image_bgr: np.ndarray) -> np.ndarray:
        torch = self._torch
        rgb = image_bgr[:, :, ::-1]
        height, width = rgb.shape[:2]
        resized = _resize_long_edge(rgb, self.max_size)
        image = self._Image.fromarray(resized)
        inputs = self.processor(images=image, return_tensors="pt")
        inputs = {key: value.to(self.device) for key, value in inputs.items()}
        try:
            with torch.inference_mode():
                prediction = self.model(**inputs).predicted_depth
        except Exception:
            if self.device != "cpu":
                self.device = "cpu"
                self.model.to("cpu")
                inputs = {key: value.to("cpu") for key, value in inputs.items()}
                with torch.inference_mode():
                    prediction = self.model(**inputs).predicted_depth
            else:
                raise
        depth = torch.nn.functional.interpolate(
            prediction.unsqueeze(1),
            size=(height, width),
            mode="bicubic",
            align_corners=False,
        ).squeeze()
        array = depth.detach().float().cpu().numpy().astype(np.float32)
        if array.ndim != 2:
            array = np.squeeze(array)
        return array


def _resize_long_edge(rgb: np.ndarray, max_size: int) -> np.ndarray:
    import cv2

    height, width = rgb.shape[:2]
    longest = max(height, width)
    if longest <= max_size:
        return rgb
    scale = max_size / float(longest)
    new_size = (max(1, int(round(width * scale))), max(1, int(round(height * scale))))
    return cv2.resize(rgb, new_size, interpolation=cv2.INTER_AREA)
