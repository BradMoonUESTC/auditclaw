from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Tuple


VALID_PROFILES = {"quick", "standard", "deep"}
RESERVED_STEP_NAMES = {"knowledge", "decompose", "audit", "logs"}


class AuditorConfigError(ValueError):
    """Raised when an auditor definition is malformed."""


@dataclass(frozen=True)
class AgentDefaults:
    backend: str = "codex"
    model: str = ""
    effort: str = "high"


@dataclass(frozen=True)
class ExtraStepDefinition:
    name: str
    template: str

    @property
    def template_filename(self) -> str:
        return self.template


@dataclass(frozen=True)
class AuditorDefinition:
    name: str
    auditor_dir: Path
    config: AgentDefaults
    profile: str
    vars: Dict[str, Any]
    extra_steps: Tuple[ExtraStepDefinition, ...]
    decompose_template_path: Path
    audit_template_path: Path
    knowledge_dir: Path | None

    def resolve_agent_options(
        self,
        *,
        backend: str | None = None,
        model: str | None = None,
        effort: str | None = None,
    ) -> Dict[str, str]:
        return {
            "backend": (backend or self.config.backend or "codex").strip(),
            "model": model if model is not None else self.config.model,
            "effort": (effort or self.config.effort or "high").strip(),
        }

    def resolve_profile(self, profile: str | None = None) -> str:
        chosen = (profile or self.profile or "standard").strip().lower()
        if chosen not in VALID_PROFILES:
            raise AuditorConfigError(
                f"Unsupported profile: {chosen!r} (valid: {', '.join(sorted(VALID_PROFILES))})"
            )
        return chosen

    def get_extra_step(self, name: str) -> ExtraStepDefinition:
        for step in self.extra_steps:
            if step.name == name:
                return step
        raise KeyError(name)

    @property
    def template_paths(self) -> Dict[str, Path]:
        paths: Dict[str, Path] = {
            "decompose": self.decompose_template_path,
            "audit": self.audit_template_path,
        }
        for step in self.extra_steps:
            paths[step.name] = self.auditor_dir / step.template
        return paths


def _ensure_file(path: Path, label: str) -> None:
    if not path.is_file():
        raise AuditorConfigError(f"Missing {label}: {path}")


def _load_json(path: Path) -> Dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AuditorConfigError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise AuditorConfigError(f"auditor.json must contain an object: {path}")
    return data


def _load_extra_steps(items: Any, auditor_dir: Path) -> Tuple[ExtraStepDefinition, ...]:
    if items is None:
        return ()
    if not isinstance(items, list):
        raise AuditorConfigError("extra_steps must be an array")

    results = []
    seen_names = set()
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise AuditorConfigError(f"extra_steps[{index}] must be an object")
        name = str(item.get("name") or "").strip()
        template = str(item.get("template") or "").strip()
        if not name or not template:
            raise AuditorConfigError(f"extra_steps[{index}] requires name and template")
        if name in RESERVED_STEP_NAMES:
            raise AuditorConfigError(f"extra_steps[{index}] uses reserved name: {name}")
        if name in seen_names:
            raise AuditorConfigError(f"Duplicate extra step name: {name}")
        _ensure_file(auditor_dir / template, f"extra step template {template}")
        seen_names.add(name)
        results.append(ExtraStepDefinition(name=name, template=template))
    return tuple(results)


def _coerce_vars(raw: Any) -> Dict[str, Any]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise AuditorConfigError("vars must be an object")
    return dict(raw)


def _coerce_config(raw: Any) -> AgentDefaults:
    if raw is None:
        return AgentDefaults()
    if not isinstance(raw, dict):
        raise AuditorConfigError("config must be an object")
    return AgentDefaults(
        backend=str(raw.get("backend") or "codex").strip() or "codex",
        model=str(raw.get("model") or "").strip(),
        effort=str(raw.get("effort") or "high").strip() or "high",
    )


def load_auditor_definition(auditor_dir: str | Path) -> AuditorDefinition:
    root = Path(auditor_dir).expanduser().resolve()
    if not root.is_dir():
        raise AuditorConfigError(f"Auditor directory does not exist: {root}")

    config_path = root / "auditor.json"
    decompose_template_path = root / "decompose.md"
    audit_template_path = root / "audit.md"
    knowledge_dir = root / "knowledge"

    _ensure_file(config_path, "auditor.json")
    _ensure_file(decompose_template_path, "decompose template")
    _ensure_file(audit_template_path, "audit template")

    raw = _load_json(config_path)
    definition = AuditorDefinition(
        name=str(raw.get("name") or root.name).strip() or root.name,
        auditor_dir=root,
        config=_coerce_config(raw.get("config")),
        profile=str(raw.get("profile") or "standard").strip().lower() or "standard",
        vars=_coerce_vars(raw.get("vars")),
        extra_steps=_load_extra_steps(raw.get("extra_steps"), root),
        decompose_template_path=decompose_template_path,
        audit_template_path=audit_template_path,
        knowledge_dir=knowledge_dir if knowledge_dir.is_dir() else None,
    )
    definition.resolve_profile()
    return definition


def validate_auditor_definition(auditor_dir: str | Path) -> AuditorDefinition:
    return load_auditor_definition(auditor_dir)


def iter_template_paths(definition: AuditorDefinition) -> Iterable[Path]:
    yield definition.decompose_template_path
    yield definition.audit_template_path
    for step in definition.extra_steps:
        yield definition.auditor_dir / step.template
