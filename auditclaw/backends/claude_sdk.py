from __future__ import annotations

import glob as glob_mod
import json
import os
from typing import Any, Optional, Dict, List

from .base import CodingAgentRunner, CodingAgentError, AgentRunResult

# ---------------------------------------------------------------------------
# config.json loader
# ---------------------------------------------------------------------------

_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config.json")
_config_cache: Optional[Dict[str, Any]] = None


def load_claude_config(config_path: str | None = None) -> Dict[str, Any]:
    """Load config.json. Returns empty dict on any failure."""
    global _config_cache
    path = config_path or _CONFIG_PATH
    if _config_cache is not None and config_path is None:
        return _config_cache
    try:
        with open(path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception:
        cfg = {}
    if config_path is None:
        _config_cache = cfg
    return cfg


def _cfg(key: str, fallback: Any = None) -> Any:
    """Get a value from config.json (only when ``enabled`` is true)."""
    cfg = load_claude_config()
    if not cfg.get("enabled", False):
        return fallback
    return cfg.get(key, fallback)


# ---------------------------------------------------------------------------
# Tool definitions for the Anthropic Messages API
# ---------------------------------------------------------------------------

_FILE_TOOLS: List[Dict[str, Any]] = [
    {
        "name": "read_file",
        "description": "Read the contents of a file at the given path (relative to workspace root).",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative file path to read."},
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Write (create or overwrite) a file at the given path. Parent directories are created automatically.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative file path to write."},
                "content": {"type": "string", "description": "File content to write."},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "list_files",
        "description": "List files matching a glob pattern relative to workspace root.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern (e.g. 'src/**/*.sol', 'report/**/*').",
                },
            },
            "required": ["pattern"],
        },
    },
]

_MAX_READ_BYTES = 512_000  # 500 KB per read


def _resolve_safe(workspace: str, rel: str) -> str:
    """Resolve *rel* under *workspace*, rejecting path traversal."""
    full = os.path.normpath(os.path.join(workspace, rel))
    if not full.startswith(os.path.normpath(workspace)):
        raise ValueError(f"Path traversal blocked: {rel}")
    return full


def _exec_tool(name: str, inp: Dict[str, Any], workspace: str) -> str:
    """Execute a tool and return the result string."""
    try:
        if name == "read_file":
            p = _resolve_safe(workspace, inp["path"])
            if not os.path.isfile(p):
                return f"[ERROR] File not found: {inp['path']}"
            size = os.path.getsize(p)
            if size > _MAX_READ_BYTES:
                return f"[ERROR] File too large ({size} bytes, limit {_MAX_READ_BYTES})."
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                return f.read()

        if name == "write_file":
            p = _resolve_safe(workspace, inp["path"])
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                f.write(inp["content"])
            return f"OK – wrote {len(inp['content'])} chars to {inp['path']}"

        if name == "list_files":
            pattern = inp.get("pattern", "**/*")
            matches = sorted(glob_mod.glob(os.path.join(workspace, pattern), recursive=True))
            rel = [os.path.relpath(m, workspace) for m in matches if os.path.isfile(m)]
            if not rel:
                return "(no files matched)"
            return "\n".join(rel[:500])

        return f"[ERROR] Unknown tool: {name}"
    except Exception as e:
        return f"[ERROR] {type(e).__name__}: {e}"


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

class ClaudeSdkRunner(CodingAgentRunner):
    """Anthropic Python SDK backend with local tool use.

    Calls the Anthropic Messages API directly and implements file tools
    (read, write, list) in-process.
    """

    def __init__(
        self,
        *,
        workspace_root: str,
        model: str = "",
        effort: str = "high",
        timeout_sec: int = 2400,
        api_key: Optional[str] = None,
        api_base_url: Optional[str] = None,
        max_tokens: int = 0,
        max_tool_rounds: int = 0,
    ) -> None:
        resolved_model = (
            model
            or _cfg("model")
            or os.environ.get("AUDIT_SHELF_MODEL")
            or os.environ.get("ANTHROPIC_MODEL")
            or "claude-opus-4-6"
        )
        resolved_key = (
            api_key
            or _cfg("api_key")
            or os.environ.get("AUDIT_SHELF_API_KEY")
            or os.environ.get("ANTHROPIC_API_KEY")
            or ""
        )
        resolved_base = (
            api_base_url
            or _cfg("api_base_url")
            or os.environ.get("AUDIT_SHELF_API_BASE")
            or os.environ.get("ANTHROPIC_BASE_URL")
        )
        resolved_max_tokens = max_tokens or int(_cfg("max_tokens", 0) or 0) or 32768
        resolved_max_rounds = max_tool_rounds or int(_cfg("max_tool_rounds", 0) or 0) or 40

        super().__init__(
            model=resolved_model,
            effort=effort,
            timeout_sec=timeout_sec,
            workspace_root=workspace_root,
        )
        self.api_key = resolved_key
        self.api_base_url = resolved_base
        self.max_tokens = resolved_max_tokens
        self.max_tool_rounds = resolved_max_rounds

    @property
    def backend_name(self) -> str:
        return "claude-sdk"

    @property
    def sandbox(self) -> str:
        return "sdk-local"

    def _build_client(self) -> Any:
        try:
            import anthropic
        except ImportError as e:
            raise CodingAgentError(
                "anthropic Python SDK not installed. Run `pip install anthropic`"
            ) from e

        os.environ.pop("ANTHROPIC_AUTH_TOKEN", None)

        kwargs: Dict[str, Any] = {
            "api_key": self.api_key,
            "timeout": float(self.timeout_sec),
        }
        if self.api_base_url:
            kwargs["base_url"] = self.api_base_url
        return anthropic.Anthropic(**kwargs)

    def run_text(
        self,
        *,
        prompt: str,
        stream_json: bool = False,
        extra_env: Optional[Dict[str, str]] = None,
    ) -> AgentRunResult:
        import warnings
        warnings.filterwarnings("ignore", message=".*thinking.type=enabled.*deprecated.*")

        client = self._build_client()

        _EFFORT_MAP = {"low": 1024, "medium": 4096, "high": 10240}
        thinking_budget = _EFFORT_MAP.get(self.effort, 10240)

        messages: List[Dict[str, Any]] = [{"role": "user", "content": prompt}]

        total_in = 0
        total_out = 0
        total_cached = 0
        all_text_parts: List[str] = []

        for _round in range(self.max_tool_rounds):
            try:
                resp = client.messages.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    thinking={
                        "type": "enabled",
                        "budget_tokens": thinking_budget,
                    },
                    tools=_FILE_TOOLS,
                    messages=messages,
                )
            except Exception as e:
                err_str = str(e)
                if "401" in err_str or "unauthorized" in err_str.lower():
                    raise CodingAgentError(
                        f"Claude SDK auth failure (401). api_base_url={self.api_base_url!r}  detail: {err_str}"
                    ) from e
                raise CodingAgentError(f"Claude SDK call failed: {err_str}") from e

            usage = resp.usage
            total_in += getattr(usage, "input_tokens", 0) or 0
            total_out += getattr(usage, "output_tokens", 0) or 0
            total_cached += getattr(usage, "cache_read_input_tokens", 0) or 0

            tool_uses: List[Dict[str, Any]] = []
            for block in resp.content:
                btype = getattr(block, "type", None)
                if btype == "text":
                    all_text_parts.append(block.text)
                elif btype == "tool_use":
                    tool_uses.append({
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    })

            if resp.stop_reason != "tool_use" or not tool_uses:
                break

            messages.append({"role": "assistant", "content": resp.content})

            tool_results = []
            for tu in tool_uses:
                result_text = _exec_tool(tu["name"], tu["input"], self.workspace_root)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tu["id"],
                    "content": result_text,
                })
            messages.append({"role": "user", "content": tool_results})

        final_text = "\n".join(all_text_parts).strip()

        return AgentRunResult(
            raw_stdout=final_text,
            raw_stderr="",
            final_text=final_text,
            input_tokens=total_in if total_in else None,
            output_tokens=total_out if total_out else None,
            cached_input_tokens=total_cached if total_cached else None,
        )

    def clone(self, **overrides: Any) -> ClaudeSdkRunner:
        overrides.pop("workspace_root", None)
        kw: Dict[str, Any] = dict(
            workspace_root=self.workspace_root,
            model=self.model,
            effort=self.effort,
            timeout_sec=self.timeout_sec,
            api_key=self.api_key,
            api_base_url=self.api_base_url,
            max_tokens=self.max_tokens,
            max_tool_rounds=self.max_tool_rounds,
        )
        kw.update(overrides)
        return ClaudeSdkRunner(**kw)
