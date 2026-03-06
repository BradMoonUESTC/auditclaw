from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
import threading
from typing import Any, Dict, Iterable, List, Sequence, Tuple

from ..agent import AgentResult, CodingAgent
from ..events import AuditEvent, EventPublisher
from ..logger import RunLogger
from .auditor_loader import ExtraStepDefinition
from .runtime_profile import RuntimeProfile, choose_parallelism
from .task_validator import TaskDescriptor
from .template_renderer import render_template_file
from .workspace_init import RuntimePaths


@dataclass(frozen=True)
class AgentCallSummary:
    tag: str
    prompt_chars: int
    response_chars: int
    elapsed_sec: float
    cost_usd: float | None
    final_text_excerpt: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tag": self.tag,
            "prompt_chars": self.prompt_chars,
            "response_chars": self.response_chars,
            "elapsed_sec": self.elapsed_sec,
            "cost_usd": self.cost_usd,
            "final_text_excerpt": self.final_text_excerpt,
        }


@dataclass(frozen=True)
class StepExecutionSummary:
    step_name: str
    output_dir: str
    call: AgentCallSummary

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_name": self.step_name,
            "output_dir": self.output_dir,
            "call": self.call.to_dict(),
        }


@dataclass(frozen=True)
class AuditTaskSummary:
    task_id: str
    instance_id: str
    task_file: str
    iterations: Tuple[AgentCallSummary, ...]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "instance_id": self.instance_id,
            "task_file": self.task_file,
            "iterations": [item.to_dict() for item in self.iterations],
        }


class RunCancelledError(RuntimeError):
    """Raised when a run is cancelled between task boundaries."""


def _sanitize_tag(value: str) -> str:
    cleaned = []
    for ch in value:
        if ch.isalnum():
            cleaned.append(ch.lower())
        elif ch in {"-", "_"}:
            cleaned.append(ch)
        else:
            cleaned.append("_")
    return "".join(cleaned).strip("_") or "step"


def _excerpt(text: str, limit: int = 300) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _summarize_call(tag: str, prompt: str, result: AgentResult) -> AgentCallSummary:
    return AgentCallSummary(
        tag=tag,
        prompt_chars=len(prompt),
        response_chars=len(result.text or ""),
        elapsed_sec=result.elapsed_sec,
        cost_usd=result.cost_usd,
        final_text_excerpt=_excerpt(result.text or ""),
    )


def _audit_iteration_prefix(iteration: int, max_iterations: int) -> str:
    if max_iterations <= 1:
        return ""
    return (
        f"This is iteration {iteration} of {max_iterations}.\n"
        "Re-read your assigned task and previous outputs.\n"
        "Read your memory and continue from the previous progress.\n"
        "Do NOT repeat already-completed work.\n\n"
    )


def _render_prompt(
    template_path: Path,
    *,
    user_vars: Dict[str, Any],
    iteration: int,
    max_iterations: int,
    fan_out_file: str | None = None,
) -> str:
    variables: Dict[str, Any] = {
        "iteration": iteration,
        "max_iterations": max_iterations,
        **user_vars,
    }
    if fan_out_file is not None:
        variables["fan_out_file"] = fan_out_file
    prompt = render_template_file(template_path, variables)
    if fan_out_file is not None:
        prompt = _audit_iteration_prefix(iteration, max_iterations) + prompt
    return prompt


def _raise_if_cancelled(cancel_event: threading.Event | None) -> None:
    if cancel_event is not None and cancel_event.is_set():
        raise RunCancelledError("Audit run was cancelled")


def run_decompose_step(
    agent: CodingAgent,
    *,
    template_path: Path,
    user_vars: Dict[str, Any],
    profile: RuntimeProfile,
    logger: RunLogger,
    output_dir: Path,
    run_id: str | None = None,
    event_publisher: EventPublisher | None = None,
    cancel_event: threading.Event | None = None,
) -> StepExecutionSummary:
    _raise_if_cancelled(cancel_event)
    if run_id and event_publisher:
        event_publisher.publish(
            AuditEvent(
                event_type="DecomposeStarted",
                run_id=run_id,
                payload={"output_dir": str(output_dir)},
            )
        )
    timer = logger.step_start("decompose", {"output_dir": str(output_dir)})
    prompt = _render_prompt(
        template_path,
        user_vars=user_vars,
        iteration=1,
        max_iterations=1,
    )
    tag = "decompose"
    result = agent.clone(timeout_sec=profile.decompose_timeout_sec).run(prompt, tag=tag)
    logger.step_end(timer, {"tag": tag})
    summary = StepExecutionSummary(
        step_name="decompose",
        output_dir=str(output_dir),
        call=_summarize_call(tag, prompt, result),
    )
    if run_id and event_publisher:
        event_publisher.publish(
            AuditEvent(
                event_type="DecomposeCompleted",
                run_id=run_id,
                payload={"output_dir": str(output_dir), "tag": tag},
            )
        )
    return summary


def run_audit_fan_out(
    agent: CodingAgent,
    *,
    template_path: Path,
    tasks: Sequence[TaskDescriptor],
    user_vars: Dict[str, Any],
    runtime_paths: RuntimePaths,
    profile: RuntimeProfile,
    logger: RunLogger,
    run_id: str | None = None,
    event_publisher: EventPublisher | None = None,
    cancel_event: threading.Event | None = None,
) -> List[AuditTaskSummary]:
    _raise_if_cancelled(cancel_event)
    worker_count = choose_parallelism(profile, len(tasks))
    timer = logger.step_start(
        "audit_fan_out",
        {"task_count": len(tasks), "worker_count": worker_count},
    )

    def run_task(task: TaskDescriptor) -> AuditTaskSummary:
        _raise_if_cancelled(cancel_event)
        task_output_dir = runtime_paths.audit_dir / task.instance_id
        task_output_dir.mkdir(parents=True, exist_ok=True)
        task_agent = agent.clone(timeout_sec=profile.audit_timeout_sec)
        iterations: List[AgentCallSummary] = []
        fan_out_file = task.relative_path.as_posix()
        if run_id and event_publisher:
            event_publisher.publish(
                AuditEvent(
                    event_type="TaskAuditStarted",
                    run_id=run_id,
                    payload={
                        "task_id": task.task_id,
                        "instance_id": task.instance_id,
                        "task_file": fan_out_file,
                    },
                )
            )

        for iteration in range(1, profile.max_audit_iterations + 1):
            _raise_if_cancelled(cancel_event)
            prompt = _render_prompt(
                template_path,
                user_vars=user_vars,
                iteration=iteration,
                max_iterations=profile.max_audit_iterations,
                fan_out_file=fan_out_file,
            )
            tag = f"audit_{_sanitize_tag(task.instance_id)}_iter_{iteration:02d}"
            result = task_agent.run(prompt, tag=tag)
            iterations.append(_summarize_call(tag, prompt, result))

        summary = AuditTaskSummary(
            task_id=task.task_id,
            instance_id=task.instance_id,
            task_file=fan_out_file,
            iterations=tuple(iterations),
        )
        if run_id and event_publisher:
            event_publisher.publish(
                AuditEvent(
                    event_type="TaskAuditCompleted",
                    run_id=run_id,
                    payload={
                        "task_id": task.task_id,
                        "instance_id": task.instance_id,
                        "task_file": fan_out_file,
                    },
                )
            )
        return summary

    results: List[AuditTaskSummary] = []
    with ThreadPoolExecutor(max_workers=worker_count) as pool:
        future_map = {pool.submit(run_task, task): task for task in tasks}
        for future in as_completed(future_map):
            results.append(future.result())

    results.sort(key=lambda item: item.instance_id)
    logger.step_end(timer, {"task_count": len(results)})
    return results


def run_extra_steps(
    agent: CodingAgent,
    *,
    extra_steps: Iterable[ExtraStepDefinition],
    auditor_dir: Path,
    user_vars: Dict[str, Any],
    runtime_paths: RuntimePaths,
    profile: RuntimeProfile,
    logger: RunLogger,
    run_id: str | None = None,
    event_publisher: EventPublisher | None = None,
    cancel_event: threading.Event | None = None,
) -> List[StepExecutionSummary]:
    results: List[StepExecutionSummary] = []
    for step in extra_steps:
        _raise_if_cancelled(cancel_event)
        output_dir = runtime_paths.extra_step_dirs[step.name]
        if run_id and event_publisher:
            event_publisher.publish(
                AuditEvent(
                    event_type="RunExtraStepStarted",
                    run_id=run_id,
                    payload={"step_name": step.name, "output_dir": str(output_dir)},
                )
            )
        timer = logger.step_start(f"extra_step:{step.name}", {"output_dir": str(output_dir)})
        prompt = _render_prompt(
            auditor_dir / step.template,
            user_vars=user_vars,
            iteration=1,
            max_iterations=1,
        )
        tag = f"extra_{_sanitize_tag(step.name)}"
        result = agent.clone(timeout_sec=profile.extra_step_timeout_sec).run(prompt, tag=tag)
        logger.step_end(timer, {"tag": tag})
        summary = StepExecutionSummary(
            step_name=step.name,
            output_dir=str(output_dir),
            call=_summarize_call(tag, prompt, result),
        )
        if run_id and event_publisher:
            event_publisher.publish(
                AuditEvent(
                    event_type="RunExtraStepCompleted",
                    run_id=run_id,
                    payload={"step_name": step.name, "output_dir": str(output_dir), "tag": tag},
                )
            )
        results.append(summary)
    return results
