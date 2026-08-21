"""Validation failures for indoor video ingestion."""

from __future__ import annotations

from typing import Any


class VideoValidationError(Exception):
    """Raised when a video cannot be accepted for preprocessing."""

    def __init__(
        self,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "details": self.details,
        }
