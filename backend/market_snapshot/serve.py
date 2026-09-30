"""Local Market Tools snapshot preview. 127.0.0.1 only. No provider HTTP."""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from market_snapshot.adapter import build_preview, combine_parlay
from market_snapshot.compat import resolve_event

STATIC = Path(__file__).resolve().parent / "static"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8766
MIME = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
}


class Handler(BaseHTTPRequestHandler):
    preview: dict = {}

    def log_message(self, fmt: str, *args) -> None:
        msg = fmt % args
        if "apiKey=" in msg or "Authorization" in msg:
            msg = "[redacted]"
        __import__("sys").stderr.write("[odds-preview] " + msg + "\n")

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, payload: dict) -> None:
        self._send(status, json.dumps(payload).encode("utf-8"), "application/json; charset=utf-8")

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path in {"/", "/index.html"}:
            return self._file("index.html")
        if path == "/api/snapshot":
            payload = {k: v for k, v in self.preview.items() if k != "quote_index"}
            return self._json(200, payload)
        if path == "/api/compat/resolve":
            qs = parse_qs(urlparse(self.path).query)
            eid = (qs.get("event_id") or [""])[0]
            return self._json(200, resolve_event(eid, self.preview.get("events") or []))
        name = path.lstrip("/")
        if (STATIC / name).is_file():
            return self._file(name)
        return self._send(404, b"Not found", "text/plain; charset=utf-8")

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return self._json(400, {"ok": False, "reason": "Invalid JSON"})
        if path != "/api/parlay":
            return self._json(404, {"ok": False, "reason": "Unknown endpoint"})
        ids = body.get("leg_ids") or []
        index = self.preview.get("quote_index") or {}
        legs = [index[i] for i in ids if i in index]
        return self._json(200, combine_parlay(legs))

    def _file(self, name: str) -> None:
        target = (STATIC / name).resolve()
        if STATIC.resolve() not in target.parents and target != STATIC.resolve():
            return self._send(403, b"Forbidden", "text/plain; charset=utf-8")
        self._send(200, target.read_bytes(), MIME.get(target.suffix, "application/octet-stream"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args(argv)
    if args.host not in {"127.0.0.1", "localhost"}:
        raise SystemExit("Preview binds to 127.0.0.1 only.")
    Handler.preview = build_preview()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print("SB ME Market Tools snapshot preview (local development only)", flush=True)
    print(f"http://{args.host}:{args.port}/", flush=True)
    print("Snapshot — not live data. NCAAF optimizer preview is unchanged on :8765.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.", flush=True)
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
