from __future__ import annotations

from typing import Optional

from .base import CodingAgentRunner
from .codex import CodexCliRunner
from .claude_sdk import ClaudeSdkRunner

_VALID_BACKENDS = ("codex", "claude-sdk")


def create_coding_agent(
    *,
    backend: str,
    workspace_root: str,
    model: str = "",
    effort: str = "high",
    timeout_sec: int = 2400,
    # Codex-specific
    sandbox: str = "workspace-write",
    auth_method: str = "apikey",
    ask_for_approval: str = "never",
    # Claude SDK
    api_key: Optional[str] = None,
    api_base_url: Optional[str] = None,
) -> CodingAgentRunner:
    """Create a CodingAgentRunner for the requested backend.

    ``backend`` must be one of ``"codex"`` or ``"claude-sdk"``.

    For ``"claude-sdk"``, configuration is resolved in this order:
      1. Explicit ``api_key`` / ``api_base_url`` arguments
      2. ``config.json`` (if ``enabled`` is true)
      3. Environment variables ``ANTHROPIC_API_KEY`` / ``ANTHROPIC_BASE_URL``
    """
    backend = (backend or "codex").strip().lower()

    if backend == "codex":
        return CodexCliRunner(
            workspace_root=workspace_root,
            model=model or "gpt-5.2",
            effort=effort,
            timeout_sec=timeout_sec,
            sandbox=sandbox,
            auth_method=auth_method,
            ask_for_approval=ask_for_approval,
        )

    if backend in ("claude-sdk", "claude"):
        return ClaudeSdkRunner(
            workspace_root=workspace_root,
            model=model or "",
            effort=effort,
            timeout_sec=timeout_sec,
            api_key=api_key,
            api_base_url=api_base_url,
        )

    raise ValueError(
        f"Unsupported backend: {backend!r} (valid: {', '.join(_VALID_BACKENDS)})"
    )
