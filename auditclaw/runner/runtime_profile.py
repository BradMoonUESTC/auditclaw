from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RuntimeProfile:
    name: str
    max_audit_iterations: int
    max_workers: int
    decompose_timeout_sec: int
    audit_timeout_sec: int
    extra_step_timeout_sec: int


_PROFILES = {
    "quick": RuntimeProfile(
        name="quick",
        max_audit_iterations=1,
        max_workers=1,
        decompose_timeout_sec=600,
        audit_timeout_sec=600,
        extra_step_timeout_sec=600,
    ),
    "standard": RuntimeProfile(
        name="standard",
        max_audit_iterations=2,
        max_workers=2,
        decompose_timeout_sec=900,
        audit_timeout_sec=900,
        extra_step_timeout_sec=900,
    ),
    "deep": RuntimeProfile(
        name="deep",
        max_audit_iterations=3,
        max_workers=3,
        decompose_timeout_sec=1500,
        audit_timeout_sec=1500,
        extra_step_timeout_sec=1500,
    ),
}


def resolve_runtime_profile(name: str) -> RuntimeProfile:
    key = (name or "standard").strip().lower()
    try:
        return _PROFILES[key]
    except KeyError as exc:
        valid = ", ".join(sorted(_PROFILES))
        raise ValueError(f"Unsupported runtime profile: {name!r} (valid: {valid})") from exc


def choose_parallelism(profile: RuntimeProfile, task_count: int) -> int:
    if task_count <= 0:
        return 1
    return min(profile.max_workers, task_count)
