"""
CodingAgent — the single top-level API of auditclaw.

Usage:
    from auditclaw import CodingAgent

    agent = CodingAgent(
        backend="claude-sdk",
        workspace="/path/to/project",
        model="claude-opus-4-6",
        effort="high",
        log_dir="./logs",
    )

    result = agent.run("Read all files and find bugs. Write findings to report/")
    print(result.text)
    print(f"Cost: ${result.cost_usd:.4f}")
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from .backends import create_coding_agent, CodingAgentRunner, CodingAgentError, AgentRunResult
from .cost import estimate_tokens, get_model_rates, estimate_cost_usd
from .env import load_workspace_env
from .logger import RunLogger


@dataclass
class AgentResult:
    """Return value of ``CodingAgent.run()``."""
    text: str
    raw_stdout: str
    raw_stderr: str
    input_tokens: Optional[int]
    output_tokens: Optional[int]
    cached_input_tokens: Optional[int]
    cost_usd: Optional[float]
    elapsed_sec: float
    tag: str
    log_dir: str


class CodingAgent:
    """High-level coding agent — the only thing you need from this SDK.

    Wraps backend creation, prompt execution, cost estimation, and structured logging
    into a single class with one method: ``run(prompt) -> AgentResult``.
    """

    def __init__(
        self,
        *,
        backend: str = "codex",
        workspace: str,
        model: str = "",
        effort: str = "high",
        timeout_sec: int = 2400,
        log_dir: Optional[str] = None,
        model_rates: Optional[Dict[str, Dict[str, float]]] = None,
        # Codex-specific
        sandbox: str = "workspace-write",
        # Claude SDK
        api_key: Optional[str] = None,
        api_base_url: Optional[str] = None,
    ) -> None:
        load_workspace_env(workspace)

        self._backend_name = backend
        self._model_rates = model_rates
        self._call_counter = 0

        self._runner: CodingAgentRunner = create_coding_agent(
            backend=backend,
            workspace_root=workspace,
            model=model,
            effort=effort,
            timeout_sec=timeout_sec,
            sandbox=sandbox,
            api_key=api_key,
            api_base_url=api_base_url,
        )

        self._log_dir = log_dir
        self._run_logger: Optional[RunLogger] = None
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
            self._run_logger = RunLogger(log_dir)

    @property
    def workspace(self) -> str:
        return self._runner.workspace_root

    @property
    def model(self) -> str:
        return self._runner.model

    @property
    def effort(self) -> str:
        return self._runner.effort

    @property
    def backend(self) -> str:
        return self._backend_name

    def run(
        self,
        prompt: str,
        *,
        tag: Optional[str] = None,
        stream_json: bool = False,
    ) -> AgentResult:
        """Execute a prompt via the coding agent. Returns ``AgentResult``."""
        self._call_counter += 1
        tag = tag or f"call_{self._call_counter:04d}"

        call_log_dir = ""
        if self._log_dir:
            call_log_dir = os.path.join(self._log_dir, tag)
            os.makedirs(call_log_dir, exist_ok=True)

        prompt_tokens_est = estimate_tokens(len(prompt))
        rate_in, rate_out, rate_cached = get_model_rates(self._runner.model, self._model_rates)

        if call_log_dir:
            with open(os.path.join(call_log_dir, f"{tag}_prompt.txt"), "w", encoding="utf-8") as f:
                f.write(prompt)

        if self._run_logger:
            self._run_logger.event("agent_call_start", {
                "tag": tag,
                "backend": self._runner.backend_name,
                "model": self._runner.model,
                "effort": self._runner.effort,
                "prompt_length": len(prompt),
                "prompt_tokens_est": prompt_tokens_est,
            })

        start = time.time()
        try:
            rr: AgentRunResult = self._runner.run_text(
                prompt=prompt,
                stream_json=stream_json,
            )
        except CodingAgentError:
            if self._run_logger:
                self._run_logger.event("agent_error", {
                    "tag": tag,
                    "elapsed": time.time() - start,
                })
            raise

        elapsed = time.time() - start

        if rr.input_tokens is not None and rr.output_tokens is not None:
            input_tokens = rr.input_tokens
            output_tokens = rr.output_tokens
            cached_tokens = rr.cached_input_tokens or 0
        else:
            input_tokens = prompt_tokens_est
            output_tokens = estimate_tokens(len(rr.final_text or ""))
            cached_tokens = 0

        if rr.cost_usd is not None:
            cost_usd = rr.cost_usd
        else:
            cost_usd = estimate_cost_usd(input_tokens, output_tokens, cached_tokens, rate_in, rate_out, rate_cached)

        if call_log_dir:
            with open(os.path.join(call_log_dir, f"{tag}_stdout.log"), "w", encoding="utf-8") as f:
                f.write(rr.raw_stdout)
            with open(os.path.join(call_log_dir, f"{tag}_stderr.log"), "w", encoding="utf-8") as f:
                f.write(rr.raw_stderr)
            call_record = {
                "tag": tag,
                "backend": self._runner.backend_name,
                "model": self._runner.model,
                "effort": self._runner.effort,
                "prompt_length": len(prompt),
                "elapsed_seconds": elapsed,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cached_input_tokens": cached_tokens,
                "cost_usd_est": cost_usd,
            }
            with open(os.path.join(call_log_dir, f"{tag}_call_record.json"), "w", encoding="utf-8") as f:
                json.dump(call_record, f, indent=2, ensure_ascii=False)

        if self._run_logger:
            self._run_logger.event("agent_ok", {
                "tag": tag,
                "backend": self._runner.backend_name,
                "model": self._runner.model,
                "elapsed": elapsed,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cached_input_tokens": cached_tokens,
                "cost_usd_est": cost_usd,
            })

        return AgentResult(
            text=rr.final_text,
            raw_stdout=rr.raw_stdout,
            raw_stderr=rr.raw_stderr,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_input_tokens=cached_tokens,
            cost_usd=cost_usd,
            elapsed_sec=elapsed,
            tag=tag,
            log_dir=call_log_dir,
        )

    def clone(self, **overrides: Any) -> CodingAgent:
        """Return a new CodingAgent with selected params overridden.

        Supported overrides: ``effort``, ``timeout_sec``, ``model``.
        ``workspace`` is never overridable (same workspace binding).
        """
        runner_overrides = {}
        for k in ("effort", "timeout_sec", "model"):
            if k in overrides:
                runner_overrides[k] = overrides.pop(k)

        new_runner = self._runner.clone(**runner_overrides)

        agent = CodingAgent.__new__(CodingAgent)
        agent._backend_name = self._backend_name
        agent._model_rates = overrides.get("model_rates", self._model_rates)
        agent._call_counter = 0
        agent._runner = new_runner
        agent._log_dir = overrides.get("log_dir", self._log_dir)
        agent._run_logger = self._run_logger
        return agent
