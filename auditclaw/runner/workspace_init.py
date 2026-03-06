from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable


@dataclass(frozen=True)
class RuntimePaths:
    workspace_root: Path
    audit_materials_root: Path
    knowledge_dir: Path
    request_path: Path
    decompose_dir: Path
    tasks_dir: Path
    audit_dir: Path
    logs_root: Path
    run_logs_dir: Path
    extra_step_dirs: Dict[str, Path]


def _reset_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def _copy_tree_contents(src: Path, dst: Path) -> None:
    if not src.is_dir():
        return
    for item in src.iterdir():
        target = dst / item.name
        if item.is_dir():
            shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)


def initialize_runtime_workspace(
    workspace_root: str | Path,
    *,
    extra_step_names: Iterable[str],
    knowledge_source: str | Path | None = None,
) -> RuntimePaths:
    root = Path(workspace_root).expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Target workspace does not exist: {root}")

    audit_materials_root = root / "audit-materials"
    knowledge_dir = audit_materials_root / "knowledge"
    request_path = audit_materials_root / "request.md"
    decompose_dir = audit_materials_root / "decompose"
    tasks_dir = decompose_dir / "tasks"
    audit_dir = audit_materials_root / "audit"
    logs_root = audit_materials_root / "logs"

    extra_step_dirs = {name: audit_materials_root / name for name in extra_step_names}

    audit_materials_root.mkdir(parents=True, exist_ok=True)
    logs_root.mkdir(parents=True, exist_ok=True)

    for path in [knowledge_dir, decompose_dir, audit_dir, *extra_step_dirs.values()]:
        _reset_dir(path)
    tasks_dir.mkdir(parents=True, exist_ok=True)

    source = Path(knowledge_source).expanduser().resolve() if knowledge_source else None
    if source and source.is_dir():
        _copy_tree_contents(source, knowledge_dir)

    base_name = datetime.now().strftime("run-%Y%m%d-%H%M%S")
    run_logs_dir = logs_root / base_name
    suffix = 1
    while run_logs_dir.exists():
        suffix += 1
        run_logs_dir = logs_root / f"{base_name}-{suffix}"
    run_logs_dir.mkdir(parents=True, exist_ok=True)

    return RuntimePaths(
        workspace_root=root,
        audit_materials_root=audit_materials_root,
        knowledge_dir=knowledge_dir,
        request_path=request_path,
        decompose_dir=decompose_dir,
        tasks_dir=tasks_dir,
        audit_dir=audit_dir,
        logs_root=logs_root,
        run_logs_dir=run_logs_dir,
        extra_step_dirs=extra_step_dirs,
    )
