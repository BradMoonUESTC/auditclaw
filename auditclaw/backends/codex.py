from __future__ import annotations

import json
import os
import subprocess
from typing import Any, Optional, Dict, List

from .base import CodingAgentRunner, CodingAgentError, AgentRunResult


def _parse_codex_jsonl(raw_stdout: str) -> dict:
    """Parse Codex stream-json output for final_text and usage."""
    result: dict = {
        "final_text": "",
        "input_tokens": None,
        "output_tokens": None,
        "cached_input_tokens": None,
    }
    if not raw_stdout:
        return result
    for line in raw_stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            evt = json.loads(line)
        except Exception:
            continue
        if not isinstance(evt, dict):
            continue
        etype = evt.get("type")
        if etype == "item.completed":
            item = evt.get("item") or {}
            if isinstance(item, dict) and item.get("type") == "agent_message":
                text = item.get("text")
                if isinstance(text, str) and text.strip():
                    result["final_text"] = text.strip()
        elif etype == "agent_message":
            text = evt.get("text")
            if isinstance(text, str) and text.strip():
                result["final_text"] = text.strip()
        elif etype == "turn.completed":
            u = evt.get("usage")
            if isinstance(u, dict):
                result["input_tokens"] = int(u.get("input_tokens") or 0) or None
                result["output_tokens"] = int(u.get("output_tokens") or 0) or None
                result["cached_input_tokens"] = int(u.get("cached_input_tokens") or 0) or None
    return result


class CodexCliRunner(CodingAgentRunner):
    """Codex CLI backend — calls the ``codex`` command-line tool as a subprocess."""

    EFFORT_SUPPORTED_MODELS = {
        "gpt-5.2", "gpt-5-codex", "gpt-5", "gpt-5-mini",
        "gpt-5-nano", "o3", "o3-mini", "o4-mini", "o1",
    }

    def __init__(
        self,
        *,
        workspace_root: str,
        model: str = "gpt-5.2",
        effort: str = "high",
        timeout_sec: int = 2400,
        sandbox: str = "workspace-write",
        auth_method: str = "apikey",
        ask_for_approval: str = "never",
    ) -> None:
        super().__init__(
            model=model,
            effort=effort,
            timeout_sec=timeout_sec,
            workspace_root=workspace_root,
        )
        self.sandbox = sandbox
        self.auth_method = auth_method
        self.ask_for_approval = ask_for_approval

    @property
    def backend_name(self) -> str:
        return "codex"

    def run_text(
        self,
        *,
        prompt: str,
        stream_json: bool = False,
        extra_env: Optional[Dict[str, str]] = None,
    ) -> AgentRunResult:
        self._ensure_cli_available("codex")

        env = os.environ.copy()
        if not env.get("OPENAI_API_KEY") and env.get("OPENAI_API_KEY_DEV"):
            env["OPENAI_API_KEY"] = env["OPENAI_API_KEY_DEV"]
        if extra_env:
            env.update(extra_env)

        cmd: List[str] = [
            "codex",
            "--ask-for-approval", self.ask_for_approval,
            "exec",
            "--config", f'preferred_auth_method="{self.auth_method}"',
            "-m", self.model,
            "-s", self.sandbox,
            "--skip-git-repo-check",
            "--cd", self.workspace_root,
        ]

        if self.model in self.EFFORT_SUPPORTED_MODELS:
            cmd.extend(["--config", f'model_reasoning_effort="{self.effort}"'])
        if stream_json:
            cmd.append("--json")

        cmd.append(prompt)

        try:
            r = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self.workspace_root,
                timeout=self.timeout_sec,
                env=env,
            )
        except subprocess.TimeoutExpired as e:
            self._handle_timeout("codex", e, self.timeout_sec, cmd)
            raise

        if r.returncode != 0:
            detail = (r.stderr or r.stdout).strip()
            if "401" in detail or "Unauthorized" in detail or "unauthorized" in detail:
                raise CodingAgentError(
                    "codex auth failure (401). Check OPENAI_API_KEY env var. "
                    f"Exit code {r.returncode}, detail: {detail}"
                )
            raise CodingAgentError(f"codex failed (exit code {r.returncode}): {detail}")

        raw_stdout = r.stdout or ""
        if stream_json:
            parsed = _parse_codex_jsonl(raw_stdout)
            return AgentRunResult(
                raw_stdout=raw_stdout,
                raw_stderr=r.stderr or "",
                final_text=parsed["final_text"],
                input_tokens=parsed["input_tokens"],
                output_tokens=parsed["output_tokens"],
                cached_input_tokens=parsed["cached_input_tokens"],
            )

        return AgentRunResult(
            raw_stdout=raw_stdout,
            raw_stderr=r.stderr or "",
            final_text=raw_stdout.strip(),
        )

    def clone(self, **overrides: Any) -> CodexCliRunner:
        overrides.pop("workspace_root", None)
        kw: Dict[str, Any] = dict(
            workspace_root=self.workspace_root,
            model=self.model,
            effort=self.effort,
            timeout_sec=self.timeout_sec,
            sandbox=self.sandbox,
            auth_method=self.auth_method,
            ask_for_approval=self.ask_for_approval,
        )
        kw.update(overrides)
        return CodexCliRunner(**kw)
