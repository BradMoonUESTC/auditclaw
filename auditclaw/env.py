from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, Set


def _iter_search_roots(workspace_root: str) -> Iterable[Path]:
    seen: Set[Path] = set()
    for raw in (workspace_root, os.getcwd()):
        try:
            start = Path(raw).expanduser().resolve()
        except FileNotFoundError:
            continue
        for path in (start, *start.parents):
            if path not in seen:
                seen.add(path)
                yield path


def load_workspace_env(workspace_root: str) -> None:
    """Load nearby ``.env`` files into ``os.environ`` without overriding existing values."""
    for root in _iter_search_roots(workspace_root):
        env_path = root / ".env"
        if not env_path.is_file():
            continue
        for line in env_path.read_text(encoding="utf-8").splitlines():
            entry = line.strip()
            if not entry or entry.startswith("#") or "=" not in entry:
                continue
            key, value = entry.split("=", 1)
            key = key.strip()
            value = value.strip()
            if not key or key in os.environ:
                continue
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
                value = value[1:-1]
            os.environ[key] = value
