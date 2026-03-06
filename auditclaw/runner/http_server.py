from __future__ import annotations

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from typing import Any
from urllib.parse import parse_qs, urlparse

from .api import AuditCoreAPI


class CoreHttpServer(ThreadingHTTPServer):
    def __init__(self, server_address, api: AuditCoreAPI):
        super().__init__(server_address, CoreHttpRequestHandler)
        self.api = api


class CoreHttpRequestHandler(BaseHTTPRequestHandler):
    server: CoreHttpServer

    def do_GET(self) -> None:
        try:
            parsed = urlparse(self.path)
            parts = [item for item in parsed.path.split("/") if item]
            if parsed.path == "/health":
                self._send_json({"status": "ok"})
                return
            if parsed.path == "/runs":
                params = parse_qs(parsed.query)
                limit = int(params.get("limit", ["20"])[0])
                payload = [item.to_dict() for item in self.server.api.list_runs(limit=limit)]
                self._send_json(payload)
                return
            if len(parts) == 2 and parts[0] == "runs":
                payload = self.server.api.get_run(parts[1]).to_dict()
                self._send_json(payload)
                return
            if len(parts) == 3 and parts[0] == "runs" and parts[2] == "tasks":
                payload = [item.__dict__ for item in self.server.api.list_tasks(parts[1])]
                self._send_json(payload)
                return
            if len(parts) == 3 and parts[0] == "runs" and parts[2] == "findings":
                payload = [item.__dict__ for item in self.server.api.list_findings(parts[1])]
                self._send_json(payload)
                return
            if parsed.path == "/artifact":
                params = parse_qs(parsed.query)
                run_id = params.get("run_id", [""])[0]
                artifact_path = params.get("path", [""])[0]
                payload = {
                    "run_id": run_id,
                    "artifact_path": artifact_path,
                    "content": self.server.api.get_artifact(run_id, artifact_path),
                }
                self._send_json(payload)
                return
            self._send_error_json(HTTPStatus.NOT_FOUND, "Not found")
        except KeyError as exc:
            self._send_error_json(HTTPStatus.NOT_FOUND, f"Unknown resource: {exc}")
        except ValueError as exc:
            self._send_error_json(HTTPStatus.BAD_REQUEST, str(exc))
        except Exception as exc:  # pragma: no cover - defensive HTTP boundary
            self._send_error_json(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))

    def do_POST(self) -> None:
        try:
            parsed = urlparse(self.path)
            parts = [item for item in parsed.path.split("/") if item]
            payload = self._read_json()
            if parsed.path == "/runs":
                run = self.server.api.start_audit_run(
                    auditor_dir=str(payload["auditor_dir"]),
                    target_path=str(payload["target_path"]),
                    profile=str(payload.get("profile", "standard")),
                    run_note=str(payload.get("run_note", "")),
                    requested_by=str(payload.get("requested_by", "http")),
                    backend=payload.get("backend"),
                    model=payload.get("model"),
                    effort=payload.get("effort"),
                    blocking=bool(payload.get("blocking", False)),
                )
                self._send_json(run.to_dict(), status=HTTPStatus.ACCEPTED)
                return
            if len(parts) == 3 and parts[0] == "runs" and parts[2] == "cancel":
                self.server.api.cancel_run(parts[1])
                self._send_json({"run_id": parts[1], "status": "cancelling"})
                return
            self._send_error_json(HTTPStatus.NOT_FOUND, "Not found")
        except KeyError as exc:
            self._send_error_json(HTTPStatus.BAD_REQUEST, f"Missing field: {exc}")
        except ValueError as exc:
            self._send_error_json(HTTPStatus.BAD_REQUEST, str(exc))
        except Exception as exc:  # pragma: no cover - defensive HTTP boundary
            self._send_error_json(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    def _send_json(self, payload: Any, *, status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_error_json(self, status: HTTPStatus, message: str) -> None:
        self._send_json({"error": message}, status=status)


def serve_core_api(*, host: str = "127.0.0.1", port: int = 8766, api: AuditCoreAPI | None = None) -> None:
    server = CoreHttpServer((host, port), api or AuditCoreAPI())
    try:
        server.serve_forever()
    finally:
        server.server_close()
