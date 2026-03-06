from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass
class StepTimer:
    name: str
    start_ts: float


class RunLogger:
    """
    Per-session structured logger.

    Writes:
    - ``<logs_root>/run.log``      — human-readable log
    - ``<logs_root>/events.jsonl`` — machine-readable event stream
    """

    def __init__(self, logs_root: str, base_logger: Optional[logging.Logger] = None) -> None:
        self.logs_root = logs_root
        os.makedirs(self.logs_root, exist_ok=True)

        self.logger = base_logger or logging.getLogger("auditclaw")
        self.logger.setLevel(self.logger.level or logging.INFO)

        log_path = os.path.join(self.logs_root, "run.log")
        self._file_handler = logging.FileHandler(log_path, encoding="utf-8")
        self._file_handler.setLevel(self.logger.level)
        self._file_handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        )
        if not any(
            isinstance(h, logging.FileHandler)
            and getattr(h, "baseFilename", "") == self._file_handler.baseFilename
            for h in self.logger.handlers
        ):
            self.logger.addHandler(self._file_handler)

        self._events_path = os.path.join(self.logs_root, "events.jsonl")

    def event(self, type_: str, payload: Dict[str, Any]) -> None:
        obj = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "type": type_,
            "payload": payload,
        }
        with open(self._events_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")

    def step_start(self, name: str, payload: Optional[Dict[str, Any]] = None) -> StepTimer:
        self.logger.info(f"[step_start] {name}")
        self.event("step_start", {"name": name, **(payload or {})})
        return StepTimer(name=name, start_ts=time.time())

    def step_end(self, timer: StepTimer, payload: Optional[Dict[str, Any]] = None) -> None:
        dur = time.time() - timer.start_ts
        self.logger.info(f"[step_end] {timer.name} duration={dur:.2f}s")
        self.event("step_end", {"name": timer.name, "duration_sec": dur, **(payload or {})})
