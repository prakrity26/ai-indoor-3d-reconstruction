"""Local mid-defense preview: selected frames + reconstructed GLB.

Does not import model/ and does not run reconstruction.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
VIEWER = Path(__file__).resolve().parent / "mesh_viewer.html"


def _job_dir(job_id: str) -> Path:
    return ROOT / "data" / "frames" / job_id


def _glb_path(job_dir: Path) -> Path:
    for candidate in (
        job_dir / "mesh.glb",
        ROOT / "data" / "outputs" / job_dir.name / "mesh.glb",
        ROOT / "samples" / job_dir.name / "mesh.glb",
    ):
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        f"No mesh.glb under {job_dir}. Run: python -m model.mesh {job_dir}"
    )


def _frame_dir(job_dir: Path) -> Path:
    selected = job_dir / "selected"
    if selected.is_dir():
        return selected
    return ROOT / "samples" / job_dir.name / "preview"


def _selected_frames(job_dir: Path, limit: int = 8) -> list[str]:
    selected = _frame_dir(job_dir)
    if not selected.is_dir():
        return []
    names = sorted(
        p.name for p in selected.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"}
    )
    if len(names) <= limit:
        return names
    step = max(1, len(names) // limit)
    picked = names[::step][:limit]
    if names[-1] not in picked:
        picked[-1] = names[-1]
    return picked


def make_handler(
    job_dir: Path, glb: Path, frames: list[str], frame_dir: Path
) -> type[BaseHTTPRequestHandler]:
    frame_set = set(frames)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: object) -> None:
            return

        def _send(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            path = unquote(urlparse(self.path).path)
            if path in {"/", "/index.html"}:
                self._send(200, VIEWER.read_bytes(), "text/html; charset=utf-8")
                return
            if path == "/mesh.glb":
                self._send(200, glb.read_bytes(), "model/gltf-binary")
                return
            if path == "/frames.json":
                payload = json.dumps({"job_id": job_dir.name, "frames": frames}).encode()
                self._send(200, payload, "application/json")
                return
            if path.startswith("/frames/"):
                name = path.rsplit("/", 1)[-1]
                if name not in frame_set:
                    self._send(404, b"not found", "text/plain")
                    return
                file_path = frame_dir / name
                mime = mimetypes.guess_type(name)[0] or "image/jpeg"
                self._send(200, file_path.read_bytes(), mime)
                return
            self._send(404, b"not found", "text/plain")

    return Handler


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Open a local mid-defense mesh preview.")
    parser.add_argument("--job-id", default="room20260814")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args(argv)

    job_dir = _job_dir(args.job_id)
    sample_dir = ROOT / "samples" / args.job_id
    if not job_dir.is_dir() and not sample_dir.is_dir():
        raise SystemExit(f"Job folder missing: {job_dir}")
    glb = _glb_path(job_dir)
    frame_dir = _frame_dir(job_dir)
    frames = _selected_frames(job_dir)
    handler = make_handler(job_dir, glb, frames, frame_dir)
    server = ThreadingHTTPServer((args.host, args.port), handler)
    url = f"http://{args.host}:{args.port}/"
    print(f"Mid-defense preview: {url}")
    print(f"Job: {job_dir}")
    print(f"Mesh: {glb}")
    print("Ctrl+C to stop.")
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
