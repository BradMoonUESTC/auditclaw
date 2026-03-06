from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable

from .backends import CodingAgentError
from .runner import (
    AuditorRunOverrides,
    preview_rendered_prompts,
    run_auditor,
    serve_core_api,
    serve_core_stdio,
    validate_auditor_definition,
)
from .runner.template_renderer import TemplateRenderError
from .runner.task_validator import TaskValidationError


def _result_to_dict(result) -> dict:
    return {
        "run_id": result.run_id,
        "auditor_name": result.auditor_name,
        "auditor_dir": result.auditor_dir,
        "target_root": result.target_root,
        "runtime_profile": result.runtime_profile,
        "dry_run": result.dry_run,
        "requested_by": result.requested_by,
        "run_note": result.run_note,
        "runtime_paths": result.runtime_paths,
        "rendered_prompts": result.rendered_prompts,
        "decompose": result.decompose.to_dict() if result.decompose else None,
        "tasks": [
            {
                "task_id": item.task_id,
                "instance_id": item.instance_id,
                "path": str(item.path),
                "relative_path": item.relative_path.as_posix(),
                "payload": item.payload,
            }
            for item in result.tasks
        ],
        "audits": [item.to_dict() for item in result.audits],
        "extra_steps": [item.to_dict() for item in result.extra_steps],
        "total_cost_usd": result.total_cost_usd,
        "summary_path": result.summary_path,
    }


def _build_overrides(args: argparse.Namespace) -> AuditorRunOverrides:
    return AuditorRunOverrides(
        backend=args.backend,
        model=args.model,
        effort=args.effort,
        profile=args.profile,
    )


def cmd_run(args: argparse.Namespace) -> int:
    result = run_auditor(
        args.auditor,
        args.target,
        overrides=_build_overrides(args),
        dry_run=args.dry_run,
        run_note=args.run_note or "",
        requested_by=args.requested_by or "cli",
    )
    print(json.dumps(_result_to_dict(result), indent=2, ensure_ascii=False))
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    definition = validate_auditor_definition(args.path)
    preview_rendered_prompts(args.path)
    payload = {
        "name": definition.name,
        "auditor_dir": str(definition.auditor_dir),
        "profile": definition.profile,
        "config": {
            "backend": definition.config.backend,
            "model": definition.config.model,
            "effort": definition.config.effort,
        },
        "templates": {
            "decompose": str(definition.decompose_template_path),
            "audit": str(definition.audit_template_path),
            "extra_steps": {step.name: step.template for step in definition.extra_steps},
        },
        "vars": definition.vars,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def cmd_render(args: argparse.Namespace) -> int:
    prompts = preview_rendered_prompts(args.path, overrides=_build_overrides(args))
    if args.template:
        try:
            text = prompts[args.template]
        except KeyError as exc:
            valid = ", ".join(sorted(prompts))
            raise SystemExit(f"Unknown template name: {args.template!r} (valid: {valid})") from exc
        print(text)
        return 0

    for index, (name, text) in enumerate(prompts.items(), start=1):
        if index > 1:
            print()
        print(f"## {name}")
        print(text)
    return 0


def _write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def cmd_init(args: argparse.Namespace) -> int:
    base_dir = Path(args.directory or "auditors").expanduser().resolve()
    target_dir = base_dir / args.name
    if target_dir.exists():
        raise SystemExit(f"Target already exists: {target_dir}")

    _write_file(
        target_dir / "auditor.json",
        json.dumps(
            {
                "name": args.name,
                "config": {"backend": "codex", "model": "gpt-5-mini", "effort": "medium"},
                "profile": "standard",
                "vars": {"task_count": 6},
                "extra_steps": [{"name": "report", "template": "report.md"}],
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
    )
    _write_file(
        target_dir / "decompose.md",
        (
            "You are a code auditor.\n\n"
            "Read the project and the knowledge files in audit-materials/knowledge/.\n"
            "If audit-materials/request.md exists, read it before deciding priorities.\n"
            "Break the project into about {{task_count}} audit tasks.\n"
            "Write each task as audit-materials/decompose/tasks/<task_id>/task.json.\n"
            "Each task.json must include at least task_id, title, and scope.\n"
            "Do not only print the tasks in chat; make sure the files are written.\n"
        ),
    )
    _write_file(
        target_dir / "audit.md",
        (
            "You are handling one audit task.\n\n"
            "Read the task file: {{fan_out_file}}\n"
            "If audit-materials/request.md exists, read it before deciding priorities.\n"
            "Derive the task directory name from the parent folder of that file.\n"
            "Write outputs under audit-materials/audit/<task_dir_name>/.\n"
            "Always update memory.md and summary.md.\n"
            "If you discover a concrete issue, immediately record it in "
            "audit-materials/audit/<task_dir_name>/finding.json.\n"
            "Keep finding.json as valid JSON and update it as you confirm more issues.\n"
            'Use the shape {"findings": [{"title": "...", "severity": "...", '
            '"affected": ["..."], "summary": "...", "root_cause": "...", '
            '"impact": "...", "remediation": "..."}]}.\n'
        ),
    )
    _write_file(
        target_dir / "report.md",
        (
            "Read all outputs under audit-materials/audit/.\n"
            "Generate a final report at audit-materials/report/final_report.md.\n"
        ),
    )
    _write_file(
        target_dir / "knowledge" / "checklist.md",
        "# Checklist\n\n- Access control\n- Input validation\n- State accounting\n",
    )
    print(str(target_dir))
    return 0


def cmd_core_serve(args: argparse.Namespace) -> int:
    serve_core_api(host=args.host, port=args.port)
    return 0


def cmd_core_mcp_serve(args: argparse.Namespace) -> int:
    serve_core_stdio()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="auditclaw")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run an auditor against a target project")
    run_parser.add_argument("--auditor", required=True, help="Path to the auditor directory")
    run_parser.add_argument("--target", required=True, help="Path to the target project")
    run_parser.add_argument("--backend", help="Override backend")
    run_parser.add_argument("--model", help="Override model")
    run_parser.add_argument("--effort", help="Override effort")
    run_parser.add_argument("--profile", help="Override profile")
    run_parser.add_argument("--run-note", help="Run-scoped note written to audit-materials/request.md")
    run_parser.add_argument("--requested-by", help="Requester identity for run metadata")
    run_parser.add_argument("--dry-run", action="store_true", help="Render prompts only")
    run_parser.set_defaults(func=cmd_run)

    validate_parser = subparsers.add_parser("validate", help="Validate an auditor directory")
    validate_parser.add_argument("path", help="Path to the auditor directory")
    validate_parser.set_defaults(func=cmd_validate)

    render_parser = subparsers.add_parser("render", help="Render prompts for an auditor")
    render_parser.add_argument("path", help="Path to the auditor directory")
    render_parser.add_argument("--template", help="Render only a specific template name")
    render_parser.add_argument("--backend", help="Override backend")
    render_parser.add_argument("--model", help="Override model")
    render_parser.add_argument("--effort", help="Override effort")
    render_parser.add_argument("--profile", help="Override profile")
    render_parser.set_defaults(func=cmd_render)

    init_parser = subparsers.add_parser("init", help="Create an auditor scaffold")
    init_parser.add_argument("name", help="New auditor name")
    init_parser.add_argument("--directory", help="Base directory for the scaffold")
    init_parser.set_defaults(func=cmd_init)

    core_parser = subparsers.add_parser("core", help="Audit Core server commands")
    core_subparsers = core_parser.add_subparsers(dest="core_command", required=True)
    core_serve = core_subparsers.add_parser("serve", help="Start the HTTP audit core server")
    core_serve.add_argument("--host", default="127.0.0.1", help="Bind host")
    core_serve.add_argument("--port", type=int, default=8766, help="Bind port")
    core_serve.set_defaults(func=cmd_core_serve)
    core_mcp = core_subparsers.add_parser("mcp-serve", help="Start the stdio core RPC bridge")
    core_mcp.set_defaults(func=cmd_core_mcp_serve)

    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        return args.func(args)
    except (CodingAgentError, TaskValidationError, TemplateRenderError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
