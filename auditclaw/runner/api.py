from __future__ import annotations

from dataclasses import dataclass, replace
import json
from pathlib import Path
import threading
from typing import Callable, Dict, List, Optional
from uuid import uuid4

from ..events import AuditEvent, EventPublisher, utc_now_iso
from .orchestrator import AuditorRunOverrides, AuditorRunResult, run_auditor


@dataclass(frozen=True)
class AuditRun:
    run_id: str
    auditor_dir: str
    target_path: str
    profile: str
    requested_by: str
    run_note: str
    status: str
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    summary_path: str | None = None
    run_logs_dir: str | None = None
    total_cost_usd: float | None = None
    error: str | None = None

    def to_dict(self) -> Dict[str, object]:
        return {
            "run_id": self.run_id,
            "auditor_dir": self.auditor_dir,
            "target_path": self.target_path,
            "profile": self.profile,
            "requested_by": self.requested_by,
            "run_note": self.run_note,
            "status": self.status,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "summary_path": self.summary_path,
            "run_logs_dir": self.run_logs_dir,
            "total_cost_usd": self.total_cost_usd,
            "error": self.error,
        }


@dataclass(frozen=True)
class TaskStatus:
    run_id: str
    task_id: str
    instance_id: str
    task_file: str
    status: str
    finding_count: int
    summary_path: str | None
    memory_path: str | None


@dataclass(frozen=True)
class FindingRecord:
    run_id: str
    task_id: str
    path: str
    title: str
    severity: str


EventListener = Callable[[AuditEvent], None]


def _parse_finding_json(path: Path) -> List[Dict[str, str]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []

    if not isinstance(payload, dict):
        return []

    findings = payload.get("findings")
    if not isinstance(findings, list):
        return []

    results: List[Dict[str, str]] = []
    for index, item in enumerate(findings, start=1):
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or f"finding-{index:02d}")
        severity = str(item.get("severity") or "unknown")
        results.append(
            {
                "title": title,
                "severity": severity,
                "path": str(path),
            }
        )
    return results


def _parse_finding_markdown(path: Path) -> Dict[str, str]:
    title = path.stem
    severity = "unknown"
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("title:"):
            title = stripped.split(":", 1)[1].strip().strip("`")
        elif stripped.lower().startswith("severity:"):
            severity = stripped.split(":", 1)[1].strip()
        if title and severity != "unknown":
            break
    return {
        "title": title,
        "severity": severity,
        "path": str(path),
    }


class AuditCoreAPI:
    """Typed API wrapper around the V2/V3 audit core."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._runs: Dict[str, AuditRun] = {}
        self._threads: Dict[str, threading.Thread] = {}
        self._cancel_events: Dict[str, threading.Event] = {}
        self._listeners: List[EventListener] = []

    def subscribe(self, listener: EventListener) -> None:
        with self._lock:
            self._listeners.append(listener)

    def start_audit_run(
        self,
        *,
        auditor_dir: str,
        target_path: str,
        profile: str = "standard",
        run_note: str = "",
        requested_by: str = "",
        backend: str | None = None,
        model: str | None = None,
        effort: str | None = None,
        blocking: bool = False,
    ) -> AuditRun:
        run_id = f"run_{uuid4().hex[:16]}"
        record = AuditRun(
            run_id=run_id,
            auditor_dir=str(Path(auditor_dir).expanduser().resolve()),
            target_path=str(Path(target_path).expanduser().resolve()),
            profile=profile,
            requested_by=requested_by,
            run_note=run_note,
            status="queued",
            created_at=utc_now_iso(),
        )
        cancel_event = threading.Event()
        event_publisher = EventPublisher()
        for listener in list(self._listeners):
            event_publisher.subscribe(listener)

        with self._lock:
            self._runs[run_id] = record
            self._cancel_events[run_id] = cancel_event

        def execute() -> None:
            self._update_run(
                run_id,
                status="running",
                started_at=utc_now_iso(),
            )
            try:
                result = run_auditor(
                    auditor_dir,
                    target_path,
                    overrides=AuditorRunOverrides(
                        backend=backend,
                        model=model,
                        effort=effort,
                        profile=profile,
                    ),
                    run_id=run_id,
                    run_note=run_note,
                    requested_by=requested_by,
                    event_publisher=event_publisher,
                    cancel_event=cancel_event,
                )
            except Exception as exc:
                status = "cancelled" if cancel_event.is_set() else "failed"
                self._update_run(
                    run_id,
                    status=status,
                    finished_at=utc_now_iso(),
                    error=str(exc),
                )
                return

            self._update_run(
                run_id,
                status="completed",
                finished_at=utc_now_iso(),
                summary_path=result.summary_path,
                run_logs_dir=result.runtime_paths["run_logs_dir"],
                total_cost_usd=result.total_cost_usd,
            )

        if blocking:
            execute()
            return self.get_run(run_id)

        thread = threading.Thread(target=execute, name=f"audit-core-{run_id}", daemon=True)
        with self._lock:
            self._threads[run_id] = thread
        thread.start()
        return self.get_run(run_id)

    def get_run(self, run_id: str) -> AuditRun:
        with self._lock:
            run = self._runs[run_id]
        return replace(run)

    def list_runs(self, limit: int = 20) -> List[AuditRun]:
        with self._lock:
            runs = sorted(self._runs.values(), key=lambda item: item.created_at, reverse=True)
        return [replace(item) for item in runs[:limit]]

    def list_tasks(self, run_id: str) -> List[TaskStatus]:
        run = self.get_run(run_id)
        tasks_root = Path(run.target_path) / "audit-materials" / "decompose" / "tasks"
        if not tasks_root.is_dir():
            return []

        results: List[TaskStatus] = []
        for task_file in sorted(tasks_root.glob("*/task.json")):
            instance_id = task_file.parent.name
            task_id = instance_id
            try:
                payload = json.loads(task_file.read_text(encoding="utf-8"))
                if isinstance(payload, dict) and payload.get("task_id"):
                    task_id = str(payload["task_id"])
            except Exception:
                pass
            audit_dir = Path(run.target_path) / "audit-materials" / "audit" / instance_id
            finding_json_path = audit_dir / "finding.json"
            summary_path = audit_dir / "summary.md"
            memory_path = audit_dir / "memory.md"
            finding_count = 0
            if audit_dir.is_dir():
                if finding_json_path.is_file():
                    finding_count = len(_parse_finding_json(finding_json_path))
                else:
                    finding_count = len(list((audit_dir / "findings").glob("*.md")))
            if summary_path.is_file():
                status = "completed"
            elif audit_dir.is_dir():
                status = "running"
            else:
                status = "pending"
            results.append(
                TaskStatus(
                    run_id=run_id,
                    task_id=task_id,
                    instance_id=instance_id,
                    task_file=str(task_file),
                    status=status,
                    finding_count=finding_count,
                    summary_path=str(summary_path) if summary_path.is_file() else None,
                    memory_path=str(memory_path) if memory_path.is_file() else None,
                )
            )
        return results

    def list_findings(self, run_id: str) -> List[FindingRecord]:
        run = self.get_run(run_id)
        findings_root = Path(run.target_path) / "audit-materials" / "audit"
        if not findings_root.is_dir():
            return []

        results: List[FindingRecord] = []
        for audit_dir in sorted(path for path in findings_root.iterdir() if path.is_dir()):
            finding_json_path = audit_dir / "finding.json"
            parsed_findings = (
                _parse_finding_json(finding_json_path)
                if finding_json_path.is_file()
                else [_parse_finding_markdown(path) for path in sorted((audit_dir / "findings").glob("*.md"))]
            )
            for item in parsed_findings:
                results.append(
                    FindingRecord(
                        run_id=run_id,
                        task_id=audit_dir.name,
                        path=item["path"],
                        title=item["title"],
                        severity=item["severity"],
                    )
                )
        return results

    def get_artifact(self, run_id: str, artifact_path: str) -> str:
        run = self.get_run(run_id)
        root = Path(run.target_path).resolve()
        path = (root / artifact_path).resolve()
        if not str(path).startswith(str(root)):
            raise ValueError(f"Artifact path escapes target root: {artifact_path}")
        return path.read_text(encoding="utf-8")

    def cancel_run(self, run_id: str) -> None:
        with self._lock:
            cancel_event = self._cancel_events[run_id]
        cancel_event.set()
        self._update_run(run_id, status="cancelling")

    def _update_run(self, run_id: str, **changes: object) -> None:
        with self._lock:
            current = self._runs[run_id]
            self._runs[run_id] = replace(current, **changes)
