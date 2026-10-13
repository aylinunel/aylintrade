"""Loopback-only dashboard with bounded background jobs and transactional event polling."""

from __future__ import annotations

import json
import re
import secrets
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import BinaryIO
from urllib.parse import parse_qs, urlsplit

from .data import Settings
from .research import execute
from .store import Store

ASSETS = {
    "/": ("index.html", "text/html"),
    "/app.js": ("app.js", "text/javascript"),
    "/style.css": ("style.css", "text/css"),
}


class StudioServer(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 16

    def __init__(self, port: int, db: Path, data: Path, reviewer: str = "rules"):
        if reviewer not in {"rules", "llm"}:
            raise ValueError("Reviewer must be rules or llm")
        self.data, self.reviewer = data, reviewer
        self.lock_file: BinaryIO | None = None
        self.token = secrets.token_urlsafe(32)
        self.busy = threading.BoundedSemaphore(1)
        self.clients = threading.BoundedSemaphore(16)
        self.worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="research")
        self.assets = {
            route: ((Path(__file__).parent / "web" / name).read_bytes(), mime)
            for route, (name, mime) in ASSETS.items()
        }
        super().__init__(("127.0.0.1", port), Handler)
        try:
            db.parent.mkdir(parents=True, exist_ok=True)
            # Ownership lasts until server_close, rather than this constructor's scope.
            self.lock_file = Path(str(db) + ".lock").open("a+b")  # noqa: SIM115
            if sys.platform == "win32":
                import msvcrt

                self.lock_file.write(b"\0")
                self.lock_file.flush()
                self.lock_file.seek(0)
                msvcrt.locking(self.lock_file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.store = Store(db)
        except OSError as exc:
            self.server_close()
            raise ValueError(
                "Cannot own the database; another studio may already be using it"
            ) from exc

    def process_request(self, request, client_address) -> None:
        if not self.clients.acquire(blocking=False):
            request.sendall(
                b"HTTP/1.1 503 Service Unavailable\r\nContent-Length: 0\r\n"
                b"Connection: close\r\n\r\n"
            )
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self.clients.release()
            raise

    def process_request_thread(self, request, client_address) -> None:
        try:
            request.settimeout(5)
            super().process_request_thread(request, client_address)
        finally:
            self.clients.release()

    def start_run(self, settings: Settings) -> str:
        if not self.busy.acquire(blocking=False):
            raise BlockingIOError("A research run is already active")
        try:
            run_id = self.store.create(settings.to_dict())

            def job() -> None:
                try:
                    execute(self.store, run_id, settings, self.data, self.reviewer)
                finally:
                    self.busy.release()

            self.worker.submit(job)
            return run_id
        except Exception:
            self.busy.release()
            raise

    def server_close(self) -> None:
        self.worker.shutdown(wait=True)
        if self.lock_file is not None:
            self.lock_file.close()
            self.lock_file = None
        super().server_close()


class Handler(BaseHTTPRequestHandler):
    server: StudioServer

    def log_message(self, _format: str, *args) -> None:
        pass  # Requests never write session headers or API keys into logs.

    def send(self, status: int, body: bytes, mime: str = "application/json") -> None:
        self.send_response(status)
        self.send_header("Content-Type", mime + "; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
            "object-src 'none'; frame-ancestors 'none'; base-uri 'none'",
        )
        self.end_headers()
        self.wfile.write(body)

    def json(self, status: int, value: object) -> None:
        self.send(status, json.dumps(value, allow_nan=False).encode())

    def host_ok(self) -> bool:
        return self.headers.get("Host") in {
            f"127.0.0.1:{self.server.server_port}",
            f"localhost:{self.server.server_port}",
        }

    def do_GET(self) -> None:
        if not self.host_ok():
            self.json(403, {"error": "Untrusted Host header"})
            return
        path = urlsplit(self.path)
        if path.path in self.server.assets:
            data, mime = self.server.assets[path.path]
            self.send(200, data, mime)
        elif path.path == "/api/session":
            self.json(200, {"token": self.server.token, "reviewer": self.server.reviewer})
        elif path.path == "/api/runs":
            self.json(200, self.server.store.runs())
        elif match := re.fullmatch(r"/api/runs/([a-f0-9]{32})(/events)?", path.path):
            run_id = match[1]
            record = self.server.store.get(run_id)
            if record is None:
                self.json(404, {"error": "Unknown run"})
            elif match[2]:
                try:
                    after = int(parse_qs(path.query).get("after", ["0"])[0])
                    if not 0 <= after < 2**63:
                        raise ValueError("after out of range")
                except ValueError:
                    self.json(400, {"error": "after must be a non-negative integer"})
                    return
                self.json(200, self.server.store.events(run_id, after))
            else:
                self.json(200, record)
        else:
            self.json(404, {"error": "Not found"})

    def do_POST(self) -> None:
        host = self.headers.get("Host", "")
        origin = self.headers.get("Origin")
        supplied = self.headers.get("X-Studio-Token", "")
        if (
            not self.host_ok()
            or origin != "http://" + host
            or not secrets.compare_digest(supplied, self.server.token)
        ):
            self.json(403, {"error": "A same-origin studio session is required"})
            return
        if self.path != "/api/runs":
            self.json(404, {"error": "Not found"})
            return
        if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
            self.json(415, {"error": "Send application/json"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 16384:
                raise ValueError("Request must be between 1 byte and 16 KiB")
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError("Settings must be a JSON object")
            settings = Settings(**payload)
            run_id = self.server.start_run(settings)
            self.json(202, {"id": run_id})
        except BlockingIOError as exc:
            self.json(409, {"error": str(exc)})
        except (ValueError, TypeError) as exc:
            self.json(400, {"error": str(exc)})


def serve(
    port: int = 8765,
    db: Path = Path("data/studio.sqlite"),
    data: Path = Path("data"),
    reviewer: str = "rules",
) -> None:
    server = StudioServer(port, db, data, reviewer)
    print(
        f"Quant Agent Studio: http://127.0.0.1:{server.server_port} · {reviewer} reviewers "
        "· paper research only"
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
