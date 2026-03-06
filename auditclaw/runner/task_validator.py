from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List


class TaskValidationError(ValueError):
    """Raised when decompose output is missing or malformed."""


@dataclass(frozen=True)
class TaskDescriptor:
    task_id: str
    instance_id: str
    path: Path
    relative_path: Path
    payload: Dict[str, Any]


def validate_task_outputs(
    tasks_dir: str | Path,
    *,
    workspace_root: str | Path | None = None,
) -> List[TaskDescriptor]:
    root = Path(tasks_dir).expanduser().resolve()
    if not root.is_dir():
        raise TaskValidationError(f"Tasks directory does not exist: {root}")

    workspace = Path(workspace_root).expanduser().resolve() if workspace_root else None
    task_files = sorted(root.glob("*/task.json"))
    if not task_files:
        raise TaskValidationError(
            "No task.json files were produced under audit-materials/decompose/tasks/"
        )

    results: List[TaskDescriptor] = []
    seen_ids = set()
    for path in task_files:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise TaskValidationError(f"Invalid JSON in task file {path}: {exc}") from exc
        if not isinstance(payload, dict):
            raise TaskValidationError(f"Task file must contain an object: {path}")
        task_id = str(payload.get("task_id") or "").strip()
        if not task_id:
            raise TaskValidationError(f"Task file missing required field 'task_id': {path}")
        if task_id in seen_ids:
            raise TaskValidationError(f"Duplicate task_id detected: {task_id}")
        seen_ids.add(task_id)
        relative_path = path.relative_to(workspace) if workspace else path.relative_to(root.parent)
        results.append(
            TaskDescriptor(
                task_id=task_id,
                instance_id=path.parent.name,
                path=path,
                relative_path=relative_path,
                payload=dict(payload),
            )
        )
    return results
