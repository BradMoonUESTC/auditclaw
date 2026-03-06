from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Callable, List

from .models import AuditEvent


EventListener = Callable[[AuditEvent], None]


class EventPublisher:
    """Local event publisher with optional JSONL persistence."""

    def __init__(self, log_path: str | Path | None = None) -> None:
        self._lock = threading.Lock()
        self._log_path = Path(log_path).expanduser().resolve() if log_path else None
        self._listeners: List[EventListener] = []

    def set_log_path(self, log_path: str | Path) -> None:
        path = Path(log_path).expanduser().resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            self._log_path = path

    def subscribe(self, listener: EventListener) -> None:
        with self._lock:
            self._listeners.append(listener)

    def publish(self, event: AuditEvent) -> None:
        with self._lock:
            log_path = self._log_path
            listeners = list(self._listeners)
        if log_path is not None:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(log_path, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")
        for listener in listeners:
            listener(event)
