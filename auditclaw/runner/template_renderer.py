from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Mapping, Set


_VAR_RE = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")


class TemplateRenderError(ValueError):
    """Raised when a template cannot be rendered."""


def extract_template_variables(template_text: str) -> Set[str]:
    return set(_VAR_RE.findall(template_text))


def render_template(template_text: str, variables: Mapping[str, Any]) -> str:
    missing = sorted(name for name in extract_template_variables(template_text) if name not in variables)
    if missing:
        raise TemplateRenderError(f"Missing template variables: {', '.join(missing)}")

    def replace(match: re.Match[str]) -> str:
        value = variables[match.group(1)]
        return str(value)

    return _VAR_RE.sub(replace, template_text)


def render_template_file(template_path: str | Path, variables: Mapping[str, Any]) -> str:
    path = Path(template_path)
    try:
        template_text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise TemplateRenderError(f"Template file not found: {path}") from exc
    return render_template(template_text, variables)
