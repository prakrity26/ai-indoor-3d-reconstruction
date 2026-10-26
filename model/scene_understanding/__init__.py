"""Object detection and 3D scene association (Phase 8)."""

from model.scene_understanding.exceptions import SceneError
from model.scene_understanding.pipeline import understand_scene

__all__ = ["SceneError", "understand_scene"]
