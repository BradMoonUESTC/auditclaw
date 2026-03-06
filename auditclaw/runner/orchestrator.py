from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
import threading
from typing import Any, Dict, List
from uuid import uuid4

from ..agent import CodingAgent
from ..events import AuditEvent, EventPublisher, utc_now_iso
from ..logger import RunLogger
from .auditor_loader import AuditorDefinition, load_auditor_definition
from .executor import (
    AuditTaskSummary,
    RunCancelledError,
    StepExecutionSummary,
    run_audit_fan_out,
    run_decompose_step,
    run_extra_steps,
)
from .runtime_profile import resolve_runtime_profile
from .task_validator import TaskDescriptor, validate_task_outputs
from .template_renderer import render_template_file
from .workspace_init import RuntimePaths, initialize_runtime_workspace


@dataclass(frozen=True)
class AuditorRunOverrides:
    backend: str | None = None
    model: str | None = None
    effort: str | None = None
    profile: str | None = None


@dataclass(frozen=True)
class AuditorRunResult:
    run_id: str
    auditor_name: str
    auditor_dir: str
    target_root: str
    runtime_profile: str
    dry_run: bool
    requested_by: str
    run_note: str
    runtime_paths: Dict[str, Any]
    rendered_prompts: Dict[str, str]
    decompose: StepExecutionSummary | None
    tasks: List[TaskDescriptor]
    audits: List[AuditTaskSummary]
    extra_steps: List[StepExecutionSummary]
    total_cost_usd: float | None
    summary_path: str | None


def _runtime_paths_payload(runtime_paths: RuntimePaths) -> Dict[str, Any]:
    return {
        "audit_materials_root": str(runtime_paths.audit_materials_root),
        "knowledge_dir": str(runtime_paths.knowledge_dir),
        "request_path": str(runtime_paths.request_path),
        "decompose_dir": str(runtime_paths.decompose_dir),
        "tasks_dir": str(runtime_paths.tasks_dir),
        "audit_dir": str(runtime_paths.audit_dir),
        "logs_root": str(runtime_paths.logs_root),
        "run_logs_dir": str(runtime_paths.run_logs_dir),
        "extra_step_dirs": {k: str(v) for k, v in runtime_paths.extra_step_dirs.items()},
    }


def _planned_runtime_paths(target_root: str | Path, extra_step_names: List[str]) -> Dict[str, Any]:
    workspace_root = Path(target_root).expanduser().resolve()
    audit_materials_root = workspace_root / "audit-materials"
    return {
        "audit_materials_root": str(audit_materials_root),
        "knowledge_dir": str(audit_materials_root / "knowledge"),
        "request_path": str(audit_materials_root / "request.md"),
        "decompose_dir": str(audit_materials_root / "decompose"),
        "tasks_dir": str(audit_materials_root / "decompose" / "tasks"),
        "audit_dir": str(audit_materials_root / "audit"),
        "logs_root": str(audit_materials_root / "logs"),
        "run_logs_dir": None,
        "extra_step_dirs": {
            name: str(audit_materials_root / name) for name in extra_step_names
        },
    }


def _build_user_vars(definition: AuditorDefinition) -> Dict[str, Any]:
    return dict(definition.vars)


def _with_audit_prefix(prompt: str, max_iterations: int) -> str:
    if max_iterations <= 1:
        return prompt
    prefix = (
        f"This is iteration 1 of {max_iterations}.\n"
        "Re-read your assigned task and previous outputs.\n"
        "Read your memory and continue from the previous progress.\n"
        "Do NOT repeat already-completed work.\n\n"
    )
    return prefix + prompt


def _compute_total_cost(
    decompose: StepExecutionSummary,
    audits: List[AuditTaskSummary],
    extra_steps: List[StepExecutionSummary],
) -> float | None:
    costs = []
    decompose_cost = decompose.call.cost_usd
    if decompose_cost is None:
        return None
    costs.append(decompose_cost)
    for audit in audits:
        for iteration in audit.iterations:
            if iteration.cost_usd is None:
                return None
            costs.append(iteration.cost_usd)
    for step in extra_steps:
        if step.call.cost_usd is None:
            return None
        costs.append(step.call.cost_usd)
    return round(sum(costs), 8)


def _render_request_context(*, run_id: str, requested_by: str, run_note: str) -> str:
    lines = [
        "# Audit Request",
        "",
        f"- run_id: {run_id}",
        f"- requested_at: {utc_now_iso()}",
        f"- requested_by: {requested_by or 'cli'}",
        "",
        "## Run Note",
        "",
        run_note.strip() or "(empty)",
        "",
    ]
    return "\n".join(lines)


def preview_rendered_prompts(
    auditor_dir: str | Path,
    *,
    overrides: AuditorRunOverrides | None = None,
) -> Dict[str, str]:
    definition = load_auditor_definition(auditor_dir)
    resolved_profile = definition.resolve_profile(overrides.profile if overrides else None)
    profile = resolve_runtime_profile(resolved_profile)
    user_vars = _build_user_vars(definition)

    rendered = {
        "decompose": render_template_file(
            definition.decompose_template_path,
            {"iteration": 1, "max_iterations": 1, **user_vars},
        ),
        "audit": _with_audit_prefix(
            render_template_file(
                definition.audit_template_path,
                {
                    "iteration": 1,
                    "max_iterations": profile.max_audit_iterations,
                    "fan_out_file": "audit-materials/decompose/tasks/example/task.json",
                    **user_vars,
                },
            ),
            profile.max_audit_iterations,
        ),
    }
    for step in definition.extra_steps:
        rendered[step.name] = render_template_file(
            definition.auditor_dir / step.template,
            {"iteration": 1, "max_iterations": 1, **user_vars},
        )
    return rendered


def run_auditor(
    auditor_dir: str | Path,
    target_root: str | Path,
    *,
    overrides: AuditorRunOverrides | None = None,
    dry_run: bool = False,
    run_id: str | None = None,
    run_note: str = "",
    requested_by: str = "",
    event_publisher: EventPublisher | None = None,
    cancel_event: threading.Event | None = None,
) -> AuditorRunResult:
    definition = load_auditor_definition(auditor_dir)
    overrides = overrides or AuditorRunOverrides()
    run_id = run_id or f"run_{uuid4().hex[:12]}"

    runtime_profile_name = definition.resolve_profile(overrides.profile)
    runtime_profile = resolve_runtime_profile(runtime_profile_name)
    user_vars = _build_user_vars(definition)
    rendered_prompts = preview_rendered_prompts(definition.auditor_dir, overrides=overrides)

    if dry_run:
        return AuditorRunResult(
            run_id=run_id,
            auditor_name=definition.name,
            auditor_dir=str(definition.auditor_dir),
            target_root=str(Path(target_root).expanduser().resolve()),
            runtime_profile=runtime_profile.name,
            dry_run=True,
            requested_by=requested_by,
            run_note=run_note,
            runtime_paths=_planned_runtime_paths(
                target_root,
                [step.name for step in definition.extra_steps],
            ),
            rendered_prompts=rendered_prompts,
            decompose=None,
            tasks=[],
            audits=[],
            extra_steps=[],
            total_cost_usd=None,
            summary_path=None,
        )

    runtime_paths = initialize_runtime_workspace(
        target_root,
        extra_step_names=[step.name for step in definition.extra_steps],
        knowledge_source=definition.knowledge_dir,
    )
    runtime_paths.request_path.write_text(
        _render_request_context(
            run_id=run_id,
            requested_by=requested_by,
            run_note=run_note,
        ),
        encoding="utf-8",
    )
    if event_publisher:
        event_publisher.set_log_path(runtime_paths.run_logs_dir / "domain_events.jsonl")
        event_publisher.publish(
            AuditEvent(
                event_type="AuditRunCreated",
                run_id=run_id,
                payload={
                    "auditor_dir": str(definition.auditor_dir),
                    "target_root": str(runtime_paths.workspace_root),
                    "profile": runtime_profile.name,
                    "requested_by": requested_by,
                },
            )
        )

    agent_options = definition.resolve_agent_options(
        backend=overrides.backend,
        model=overrides.model,
        effort=overrides.effort,
    )
    run_logger = RunLogger(str(runtime_paths.run_logs_dir))
    agent = CodingAgent(
        backend=agent_options["backend"],
        workspace=str(runtime_paths.workspace_root),
        model=agent_options["model"],
        effort=agent_options["effort"],
        timeout_sec=max(
            runtime_profile.decompose_timeout_sec,
            runtime_profile.audit_timeout_sec,
            runtime_profile.extra_step_timeout_sec,
        ),
        log_dir=str(runtime_paths.run_logs_dir / "agent"),
    )
    try:
        decompose = run_decompose_step(
            agent,
            template_path=definition.decompose_template_path,
            user_vars=user_vars,
            profile=runtime_profile,
            logger=run_logger,
            output_dir=runtime_paths.decompose_dir,
            run_id=run_id,
            event_publisher=event_publisher,
            cancel_event=cancel_event,
        )

        tasks = validate_task_outputs(
            runtime_paths.tasks_dir,
            workspace_root=runtime_paths.workspace_root,
        )
        if event_publisher:
            event_publisher.publish(
                AuditEvent(
                    event_type="TasksValidated",
                    run_id=run_id,
                    payload={"task_count": len(tasks)},
                )
            )

        audits = run_audit_fan_out(
            agent,
            template_path=definition.audit_template_path,
            tasks=tasks,
            user_vars=user_vars,
            runtime_paths=runtime_paths,
            profile=runtime_profile,
            logger=run_logger,
            run_id=run_id,
            event_publisher=event_publisher,
            cancel_event=cancel_event,
        )

        extra_steps = run_extra_steps(
            agent,
            extra_steps=definition.extra_steps,
            auditor_dir=definition.auditor_dir,
            user_vars=user_vars,
            runtime_paths=runtime_paths,
            profile=runtime_profile,
            logger=run_logger,
            run_id=run_id,
            event_publisher=event_publisher,
            cancel_event=cancel_event,
        )
        total_cost_usd = _compute_total_cost(decompose, audits, extra_steps)

        summary_path = runtime_paths.run_logs_dir / "run_summary.json"
        summary_payload = {
            "run_id": run_id,
            "auditor_name": definition.name,
            "auditor_dir": str(definition.auditor_dir),
            "target_root": str(runtime_paths.workspace_root),
            "runtime_profile": runtime_profile.name,
            "requested_by": requested_by,
            "run_note": run_note,
            "runtime_paths": _runtime_paths_payload(runtime_paths),
            "decompose": decompose.to_dict(),
            "tasks": [
                {
                    "task_id": item.task_id,
                    "instance_id": item.instance_id,
                    "path": str(item.path),
                    "relative_path": item.relative_path.as_posix(),
                }
                for item in tasks
            ],
            "audits": [item.to_dict() for item in audits],
            "extra_steps": [item.to_dict() for item in extra_steps],
            "total_cost_usd": total_cost_usd,
        }
        summary_path.write_text(json.dumps(summary_payload, indent=2, ensure_ascii=False), encoding="utf-8")
        if event_publisher:
            event_publisher.publish(
                AuditEvent(
                    event_type="AuditRunCompleted",
                    run_id=run_id,
                    payload={"summary_path": str(summary_path), "total_cost_usd": total_cost_usd},
                )
            )

        return AuditorRunResult(
            run_id=run_id,
            auditor_name=definition.name,
            auditor_dir=str(definition.auditor_dir),
            target_root=str(runtime_paths.workspace_root),
            runtime_profile=runtime_profile.name,
            dry_run=False,
            requested_by=requested_by,
            run_note=run_note,
            runtime_paths=_runtime_paths_payload(runtime_paths),
            rendered_prompts=rendered_prompts,
            decompose=decompose,
            tasks=tasks,
            audits=audits,
            extra_steps=extra_steps,
            total_cost_usd=total_cost_usd,
            summary_path=str(summary_path),
        )
    except RunCancelledError:
        if event_publisher:
            event_publisher.publish(
                AuditEvent(
                    event_type="AuditRunCancelled",
                    run_id=run_id,
                    payload={"target_root": str(runtime_paths.workspace_root)},
                )
            )
        raise
    except Exception as exc:
        if event_publisher:
            event_publisher.publish(
                AuditEvent(
                    event_type="AuditRunFailed",
                    run_id=run_id,
                    payload={"error": str(exc)},
                )
            )
        raise
