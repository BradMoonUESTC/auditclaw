from __future__ import annotations

import os
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional, Dict


class CodingAgentError(RuntimeError):
    pass


@dataclass
class AgentRunResult:
    raw_stdout: str
    raw_stderr: str
    final_text: str
    json_obj: Optional[Dict[str, Any]] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    cached_input_tokens: Optional[int] = None
    cost_usd: Optional[float] = None


class CodingAgentRunner(ABC):
    """
    Coding Agent abstract base.

    workspace_root is bound at construction time and immutable across all
    run_text() invocations.  Subclasses implement the actual CLI call
    (Codex, Claude Code, etc.).
    """

    def __init__(
        self,
        *,
        model: str,
        effort: str = "high",
        timeout_sec: int = 2400,
        workspace_root: str,
    ) -> None:
        self.model = model
        self.effort = effort
        self.timeout_sec = timeout_sec
        self._workspace_root = os.path.abspath(os.path.expanduser(workspace_root))
        if not os.path.isdir(self._workspace_root):
            raise CodingAgentError(f"workspace_root does not exist: {self._workspace_root}")

    @property
    def workspace_root(self) -> str:
        return self._workspace_root

    @property
    def reasoning_effort(self) -> str:
        return self.effort

    @property
    @abstractmethod
    def backend_name(self) -> str:
        ...

    @abstractmethod
    def run_text(
        self,
        *,
        prompt: str,
        stream_json: bool = False,
        extra_env: Optional[Dict[str, str]] = None,
    ) -> AgentRunResult:
        ...

    @abstractmethod
    def clone(self, **overrides: Any) -> CodingAgentRunner:
        """Return a copy with selected params overridden.  workspace_root is never overridable."""
        ...

    @staticmethod
    def _ensure_cli_available(cli_name: str) -> None:
        try:
            r = subprocess.run(
                [cli_name, "--version"],
                capture_output=True, text=True, timeout=10,
            )
        except Exception as e:
            raise CodingAgentError(f"Cannot execute {cli_name}: {e}") from e
        if r.returncode != 0:
            raise CodingAgentError(
                f"{cli_name} unavailable (exit code {r.returncode}): "
                f"{(r.stderr or r.stdout).strip()}"
            )

    @staticmethod
    def _handle_timeout(cli_name: str, e: subprocess.TimeoutExpired, timeout_sec: int, cmd: list) -> None:
        raw_out = e.stdout or ""
        raw_err = e.stderr or ""
        tail = (raw_err or raw_out).strip()
        tail_hint = f" last output: {tail}" if tail else ""
        raise CodingAgentError(
            f"{cli_name} timed out (>{timeout_sec}s).{tail_hint}"
        ) from e
