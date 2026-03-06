# auditclaw

[Chinese README / 中文文档](./README_CN.md)

`auditclaw` is an agent-driven audit core for code and smart contract review workflows. Its core value is simple: any auditor can turn their own audit knowledge into a custom AI scanning engine by writing the methodology into the auditor's `Markdown` files, while the framework handles task decomposition, fan-out execution, artifact capture, and run logging.

In practice, that means the auditor focuses on prompts, checklists, heuristics, and reporting structure in files like `decompose.md`, `audit.md`, `report.md`, and `knowledge/*.md`. `auditclaw` turns those assets into an executable audit pipeline instead of requiring each auditor to build a new agent system from scratch.

This repository currently implements the `Audit Core` only. It already provides the core scanning and audit execution pipeline, but it does **not** yet include the outer automation layer you might expect from something like `openclaw`, such as target onboarding, scheduling, notifications, ticket routing, external integrations, or broader operational orchestration.

## Core Design

`auditclaw` is intentionally not a general-purpose workflow engine. The design focuses on a fixed audit skeleton that is stable, reusable, and easy to operationalize:

1. Use `decompose.md` to break the target project into standardized audit tasks.
2. Validate the generated task artifacts before execution.
3. Run `audit.md` against each task in parallel.
4. Persist per-task outputs such as `memory.md`, `summary.md`, and `finding.json`.
5. Execute optional `extra_steps` after the core scan finishes, for example report synthesis.

This separation keeps the methodology in files like `auditor.json`, `decompose.md`, `audit.md`, `report.md`, and `knowledge/`, while the runtime layer owns concurrency, logging, event publishing, cost collection, and artifact layout.

## Auditor Definition

An auditor is just a folder, typically shaped like this:

```text
auditors/
└── my-auditor/
    ├── auditor.json
    ├── decompose.md
    ├── audit.md
    ├── report.md
    └── knowledge/
        └── checklist.md
```

In that structure:

- `auditor.json` defines backend, model, runtime profile, variables, and extra steps.
- `decompose.md` encodes how the auditor wants an AI to break a target into audit tasks.
- `audit.md` encodes how the auditor wants each task to be reviewed.
- `knowledge/` stores checklist material and domain knowledge that can be injected into the scan.
- `extra_steps` are used for post-processing after the core scan completes.

The key idea is that the auditor writes expertise into these `md` assets, and `auditclaw` turns that expertise into a repeatable AI scanning engine.

## Runtime Layout

When a run starts, `auditclaw` creates a fixed `audit-materials/` layout under the target project root:

```text
target-project/
└── audit-materials/
    ├── knowledge/
    ├── decompose/
    │   └── tasks/
    ├── audit/
    │   └── <task_id>/
    │       ├── memory.md
    │       ├── summary.md
    │       └── finding.json
    ├── report/
    └── logs/
```

The important contract is:

- `decompose` must emit standardized `task.json` files
- `audit` must write outputs into each task-specific directory
- confirmed issues should be persisted to that task's `finding.json` during the audit process

## Scope And Non-Goals

What `auditclaw` already covers:

- audit task decomposition
- parallel fan-out task auditing
- structured findings capture
- post-processing steps for report generation
- HTTP, stdio, and Python API access to the audit core
- run logs, event streams, and cost accounting

What it does **not** yet include:

- `openclaw`-style target onboarding and lifecycle management
- scheduling, retries, queue management, and broader orchestration
- notification, approval, ticketing, or collaboration workflows
- persistent platform-level automation around long-running audit operations
- full external integration and closed-loop operational automation

The current repository should be understood as the core execution engine, not the full surrounding platform.

## Quick Start

Use the CLI:

```bash
auditclaw init demo-auditor
auditclaw validate ./auditors/example-sol-audit
auditclaw run --auditor ./auditors/example-sol-audit --target ./bankroll
```

Or call it from Python:

```python
from auditclaw.runner import run_auditor

result = run_auditor(
    "./auditors/example-sol-audit",
    "./bankroll",
)

print(result.summary_path)
```

If you need to expose the core to external systems, you can also run the HTTP server or the stdio RPC bridge.