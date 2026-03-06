from __future__ import annotations

import io
import json
import os
import re
import shutil
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from urllib import request
from unittest.mock import patch

from auditclaw.agent import AgentResult
from auditclaw.cli import main as cli_main
from auditclaw.env import load_workspace_env
from auditclaw.runner import AuditCoreAPI, CoreHttpServer, preview_rendered_prompts, run_auditor, serve_core_stdio
from auditclaw.runner.task_validator import TaskValidationError, validate_task_outputs
from auditclaw.runner.template_renderer import TemplateRenderError, render_template


REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_AUDITOR = REPO_ROOT / "auditors" / "example-sol-audit"
BANKROLL = REPO_ROOT / "bankroll"


def copy_bankroll_fixture(target: Path) -> None:
    shutil.copytree(
        BANKROLL,
        target,
        ignore=shutil.ignore_patterns("audit-materials"),
    )


class FakeCodingAgent:
    def __init__(
        self,
        *,
        backend: str = "fake",
        workspace: str,
        model: str = "",
        effort: str = "medium",
        timeout_sec: int = 0,
        log_dir: str | None = None,
        model_rates=None,
        sandbox: str = "workspace-write",
        api_key: str | None = None,
        api_base_url: str | None = None,
    ) -> None:
        self.backend = backend
        self.workspace = Path(workspace)
        self.model = model
        self.effort = effort
        self.timeout_sec = timeout_sec
        self.log_dir = log_dir or ""

    def clone(self, **overrides):
        return FakeCodingAgent(
            backend=overrides.get("backend", self.backend),
            workspace=str(self.workspace),
            model=overrides.get("model", self.model),
            effort=overrides.get("effort", self.effort),
            timeout_sec=overrides.get("timeout_sec", self.timeout_sec),
            log_dir=overrides.get("log_dir", self.log_dir),
        )

    def run(self, prompt: str, *, tag: str | None = None, stream_json: bool = False) -> AgentResult:
        tag = tag or "call"
        if tag == "decompose":
            sol_files = sorted(self.workspace.glob("*.sol"))
            tasks_root = self.workspace / "audit-materials" / "decompose" / "tasks"
            for index, sol_file in enumerate(sol_files, start=1):
                task_id = f"T{index:03d}"
                task_dir = tasks_root / task_id
                task_dir.mkdir(parents=True, exist_ok=True)
                task = {
                    "task_id": task_id,
                    "title": f"Review {sol_file.name}",
                    "scope": sol_file.name,
                    "targets": {"primary_files": [sol_file.name]},
                }
                (task_dir / "task.json").write_text(
                    json.dumps(task, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
            text = f"created {len(sol_files)} tasks"
            return self._result(text, tag, 0.01)

        if tag.startswith("audit_"):
            match = re.search(
                r"audit-materials/decompose/tasks/([^/]+)/task\.json",
                prompt,
            )
            if not match:
                raise AssertionError(f"task path missing from prompt: {prompt}")
            task_folder = match.group(1)
            task_output_dir = self.workspace / "audit-materials" / "audit" / task_folder
            task_output_dir.mkdir(parents=True, exist_ok=True)
            (task_output_dir / "memory.md").write_text(
                f"# Memory\n\nReviewed {task_folder}.\n",
                encoding="utf-8",
            )
            (task_output_dir / "summary.md").write_text(
                f"# Summary\n\nChecked task {task_folder}.\n",
                encoding="utf-8",
            )
            if task_folder == "T001":
                (task_output_dir / "finding.json").write_text(
                    json.dumps(
                        {
                            "findings": [
                                {
                                    "title": "Potential accounting mismatch",
                                    "severity": "High",
                                    "affected": ["Bankroll.sol", "settle()"],
                                    "summary": "Potential accounting mismatch.",
                                    "root_cause": "State updates can diverge from token balances.",
                                    "impact": "Users may receive incorrect balances.",
                                    "remediation": "Align accounting with actual token movement.",
                                }
                            ]
                        },
                        indent=2,
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
            text = f"audited {task_folder}"
            return self._result(text, tag, 0.02)

        if tag.startswith("extra_"):
            report_dir = self.workspace / "audit-materials" / "report"
            report_dir.mkdir(parents=True, exist_ok=True)
            (report_dir / "final_report.md").write_text(
                "# Final Report\n\nOne simulated finding.\n",
                encoding="utf-8",
            )
            return self._result("report ready", tag, 0.03)

        return self._result("ok", tag, 0.0)

    def _result(self, text: str, tag: str, cost_usd: float) -> AgentResult:
        return AgentResult(
            text=text,
            raw_stdout=text,
            raw_stderr="",
            input_tokens=10,
            output_tokens=5,
            cached_input_tokens=0,
            cost_usd=cost_usd,
            elapsed_sec=0.01,
            tag=tag,
            log_dir=self.log_dir,
        )


class V2RunnerTests(unittest.TestCase):
    def test_render_template_requires_defined_vars(self) -> None:
        with self.assertRaises(TemplateRenderError):
            render_template("hello {{name}} {{missing}}", {"name": "world"})

    def test_load_workspace_env_reads_parent_dotenv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "target"
            workspace.mkdir()
            (root / ".env").write_text("TEST_AUDIT_SHELF_ENV=loaded\n", encoding="utf-8")
            old_value = os.environ.pop("TEST_AUDIT_SHELF_ENV", None)
            try:
                load_workspace_env(str(workspace))
                self.assertEqual(os.environ.get("TEST_AUDIT_SHELF_ENV"), "loaded")
            finally:
                os.environ.pop("TEST_AUDIT_SHELF_ENV", None)
                if old_value is not None:
                    os.environ["TEST_AUDIT_SHELF_ENV"] = old_value

    def test_validate_task_outputs_requires_task_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tasks_dir = Path(tmp) / "tasks" / "bad-task"
            tasks_dir.mkdir(parents=True)
            (tasks_dir / "task.json").write_text('{"title": "missing id"}', encoding="utf-8")
            with self.assertRaises(TaskValidationError):
                validate_task_outputs(tasks_dir.parent)

    def test_preview_prompts_include_iteration_prefix(self) -> None:
        prompts = preview_rendered_prompts(EXAMPLE_AUDITOR)
        self.assertIn("This is iteration 1 of 2.", prompts["audit"])
        self.assertIn("audit-materials/decompose/tasks/example/task.json", prompts["audit"])

    def test_run_auditor_dry_run_is_side_effect_free(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            copy_bankroll_fixture(target)
            result = run_auditor(EXAMPLE_AUDITOR, target, dry_run=True)
            self.assertFalse((target / "audit-materials").exists())
            self.assertTrue(result.dry_run)
            self.assertIsNone(result.runtime_paths["run_logs_dir"])

    def test_run_auditor_end_to_end_on_bankroll_copy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            copy_bankroll_fixture(target)
            with patch("auditclaw.runner.orchestrator.CodingAgent", FakeCodingAgent):
                result = run_auditor(
                    EXAMPLE_AUDITOR,
                    target,
                    run_note="focus token flows",
                    requested_by="tester",
                )
            self.assertEqual(len(result.tasks), 2)
            self.assertIsNotNone(result.decompose)
            self.assertAlmostEqual(result.total_cost_usd, 0.12, places=6)
            self.assertTrue(result.run_id.startswith("run_"))
            self.assertTrue((target / "audit-materials" / "knowledge" / "vuln_checklist.md").is_file())
            self.assertTrue((target / "audit-materials" / "request.md").is_file())
            self.assertTrue((target / "audit-materials" / "report" / "final_report.md").is_file())
            self.assertTrue(Path(result.summary_path).is_file())

    def test_cli_init_and_validate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                exit_code = cli_main(["init", "demo-audit", "--directory", tmp])
            self.assertEqual(exit_code, 0)
            scaffold_dir = Path(tmp) / "demo-audit"
            self.assertTrue((scaffold_dir / "auditor.json").is_file())

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                exit_code = cli_main(["validate", str(scaffold_dir)])
            self.assertEqual(exit_code, 0)
            self.assertIn('"name": "demo-audit"', stdout.getvalue())

    def test_audit_core_api_exposes_runs_tasks_findings_and_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            copy_bankroll_fixture(target)
            api = AuditCoreAPI()
            event_types: list[str] = []
            api.subscribe(lambda event: event_types.append(event.event_type))
            with patch("auditclaw.runner.orchestrator.CodingAgent", FakeCodingAgent):
                run = api.start_audit_run(
                    auditor_dir=str(EXAMPLE_AUDITOR),
                    target_path=str(target),
                    profile="quick",
                    run_note="focus withdraw",
                    requested_by="api-test",
                    blocking=True,
                )
            self.assertEqual(run.status, "completed")
            self.assertIn("TasksValidated", event_types)
            self.assertIn("AuditRunCompleted", event_types)

            tasks = api.list_tasks(run.run_id)
            findings = api.list_findings(run.run_id)
            report = api.get_artifact(run.run_id, "audit-materials/report/final_report.md")

            self.assertEqual(len(tasks), 2)
            self.assertEqual(tasks[0].finding_count, 1)
            self.assertGreaterEqual(len(findings), 1)
            self.assertIn("Final Report", report)
            self.assertEqual(findings[0].severity, "High")

    def test_core_http_server_endpoints(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            copy_bankroll_fixture(target)
            api = AuditCoreAPI()
            server = CoreHttpServer(("127.0.0.1", 0), api)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address
            base = f"http://{host}:{port}"
            try:
                with patch("auditclaw.runner.orchestrator.CodingAgent", FakeCodingAgent):
                    payload = json.dumps(
                        {
                            "auditor_dir": str(EXAMPLE_AUDITOR),
                            "target_path": str(target),
                            "profile": "quick",
                            "blocking": True,
                        }
                    ).encode("utf-8")
                    req = request.Request(
                        f"{base}/runs",
                        data=payload,
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    )
                    response = json.loads(request.urlopen(req).read().decode("utf-8"))
                run_id = response["run_id"]
                health = json.loads(request.urlopen(f"{base}/health").read().decode("utf-8"))
                runs = json.loads(request.urlopen(f"{base}/runs?limit=5").read().decode("utf-8"))
                tasks = json.loads(request.urlopen(f"{base}/runs/{run_id}/tasks").read().decode("utf-8"))
                findings = json.loads(request.urlopen(f"{base}/runs/{run_id}/findings").read().decode("utf-8"))
                artifact = json.loads(
                    request.urlopen(
                        f"{base}/artifact?run_id={run_id}&path=audit-materials/report/final_report.md"
                    ).read().decode("utf-8")
                )
                self.assertEqual(health["status"], "ok")
                self.assertEqual(runs[0]["run_id"], run_id)
                self.assertEqual(len(tasks), 2)
                self.assertGreaterEqual(len(findings), 1)
                self.assertIn("Final Report", artifact["content"])
            finally:
                server.shutdown()
                server.server_close()

    def test_core_stdio_server_protocol(self) -> None:
        api = AuditCoreAPI()
        stdin = io.StringIO(
            json.dumps({"id": "1", "method": "health", "params": {}}) + "\n"
            + json.dumps({"id": "2", "method": "list_runs", "params": {"limit": 5}}) + "\n"
            + json.dumps({"id": "3", "method": "shutdown", "params": {}}) + "\n"
        )
        stdout = io.StringIO()
        serve_core_stdio(api=api, stdin=stdin, stdout=stdout)
        rows = [json.loads(line) for line in stdout.getvalue().splitlines() if line.strip()]
        self.assertEqual(rows[0]["result"]["status"], "ok")
        self.assertEqual(rows[1]["result"], [])
        self.assertEqual(rows[2]["result"]["status"], "bye")

    def test_cli_core_commands(self) -> None:
        stdin = io.StringIO(
            json.dumps({"id": "1", "method": "health", "params": {}}) + "\n"
            + json.dumps({"id": "2", "method": "shutdown", "params": {}}) + "\n"
        )
        stdout = io.StringIO()
        import sys

        old_stdin = sys.stdin
        old_stdout = sys.stdout
        try:
            sys.stdin = stdin
            sys.stdout = stdout
            exit_code = cli_main(["core", "mcp-serve"])
        finally:
            sys.stdin = old_stdin
            sys.stdout = old_stdout
        self.assertEqual(exit_code, 0)
        rows = [json.loads(line) for line in stdout.getvalue().splitlines() if line.strip()]
        self.assertEqual(rows[0]["result"]["status"], "ok")


if __name__ == "__main__":
    unittest.main()
