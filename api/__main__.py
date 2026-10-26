"""Run the upload API. Training stays in the worker, not in this process."""

from __future__ import annotations

import os

import uvicorn


def main() -> None:
    uvicorn.run(
        "api.app:app",
        host=os.environ.get("API_HOST", "0.0.0.0"),
        port=int(os.environ.get("API_PORT", "8000")),
        reload=False,
    )


if __name__ == "__main__":
    main()
