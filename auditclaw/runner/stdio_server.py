from __future__ import annotations

import json
import sys
from typing import IO, Any, Callable

from .api import AuditCoreAPI


def serve_core_stdio(
    *,
    api: AuditCoreAPI | None = None,
    stdin: IO[str] | None = None,
    stdout: IO[str] | None = None,
) -> None:
    core = api or AuditCoreAPI()
    instream = stdin or sys.stdin
    outstream = stdout or sys.stdout

    methods: dict[str, Callable[..., Any]] = {
        "health": lambda: {"status": "ok"},
        "start_audit_run": core.start_audit_run,
        "get_run": core.get_run,
        "list_runs": core.list_runs,
        "list_tasks": core.list_tasks,
        "list_findings": core.list_findings,
        "get_artifact": core.get_artifact,
        "cancel_run": core.cancel_run,
    }

    for raw_line in instream:
        line = raw_line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            if not isinstance(request, dict):
                raise ValueError("Request must be a JSON object")
            request_id = request.get("id")
            method_name = str(request.get("method") or "")
            params = request.get("params") or {}
            if not isinstance(params, dict):
                raise ValueError("params must be an object")
            if method_name == "shutdown":
                response = {"id": request_id, "result": {"status": "bye"}}
                outstream.write(json.dumps(response, ensure_ascii=False) + "\n")
                outstream.flush()
                break
            method = methods.get(method_name)
            if method is None:
                raise KeyError(method_name)
            result = method(**params)
            if hasattr(result, "to_dict"):
                result = result.to_dict()
            elif isinstance(result, list):
                result = [item.to_dict() if hasattr(item, "to_dict") else getattr(item, "__dict__", item) for item in result]
            elif hasattr(result, "__dict__") and not isinstance(result, dict):
                result = result.__dict__
            response = {"id": request_id, "result": result}
        except Exception as exc:
            response = {
                "id": request.get("id") if isinstance(locals().get("request"), dict) else None,
                "error": {"type": type(exc).__name__, "message": str(exc)},
            }
        outstream.write(json.dumps(response, ensure_ascii=False) + "\n")
        outstream.flush()
