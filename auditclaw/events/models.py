from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class AuditEvent:
    event_type: str
    run_id: str
    payload: Dict[str, Any] = field(default_factory=dict)
    ts: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ts": self.ts,
            "event_type": self.event_type,
            "run_id": self.run_id,
            "payload": self.payload,
        }
