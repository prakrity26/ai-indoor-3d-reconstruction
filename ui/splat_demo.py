"""Serve the walkable splat viewer. Needs point_cloud.ply from GPU training."""

from __future__ import annotations

import argparse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIEWER = Path(__file__).resolve().parent / "splat_viewer.html"


def find_ply(job_id: str) -> Path | None:
    for candidate in (
        ROOT / "data" / "frames" / job_id / "splat" / "point_cloud.ply",
        ROOT / "data" / "outputs" / job_id / "point_cloud.ply",
    ):
        if candidate.is_file() and candidate.stat().st_size > 0:
            return candidate
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Walkable splat preview (WASD).")
    parser.add_argument("--job-id", default="img7916")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args(argv)

    ply = find_ply(args.job_id)
    handler_ply = ply

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *a: object) -> None:
            return

        def do_GET(self) -> None:  # noqa: N802
            if self.path in {"/", "/index.html"}:
                body = VIEWER.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if self.path == "/splat.ply":
                if handler_ply is None:
                    self.send_response(404)
                    self.end_headers()
                    self.wfile.write(b"no splat ply yet")
                    return
                body = handler_ply.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_response(404)
            self.end_headers()

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    url = f"http://{args.host}:{args.port}/"
    print(f"Walkable splat viewer: {url}", flush=True)
    if ply:
        print(f"PLY: {ply}", flush=True)
    else:
        print(
            f"No point_cloud.ply for job {args.job_id} yet. "
            "Train on Colab, download the ply, then restart this command.",
            flush=True,
        )
        print("You can still open the page and load a ply with the file picker.", flush=True)
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
