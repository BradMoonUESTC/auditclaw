"""Self-contained cost estimation — no external dependencies."""
from __future__ import annotations

import math
from typing import Dict, Optional, Tuple

# Built-in model pricing ($/1M tokens).
# Users can override via CodingAgent(model_rates={...}).
MODEL_RATES: Dict[str, Dict[str, float]] = {
    # OpenAI / Codex
    "gpt-5.2": {"input": 2.0, "output": 8.0, "cached": 0.0},
    "gpt-5": {"input": 2.0, "output": 8.0, "cached": 0.0},
    "gpt-5-mini": {"input": 0.4, "output": 1.6, "cached": 0.0},
    "o3": {"input": 2.0, "output": 8.0, "cached": 0.0},
    "o3-mini": {"input": 1.1, "output": 4.4, "cached": 0.0},
    "o4-mini": {"input": 1.1, "output": 4.4, "cached": 0.0},
    # Anthropic / Claude
    "claude-opus-4-6": {"input": 5.5, "output": 27.5, "cached": 0.55},
    "opus": {"input": 5.5, "output": 27.5, "cached": 0.55},
    "claude-4-opus": {"input": 5.5, "output": 27.5, "cached": 0.55},
    "claude-4-sonnet": {"input": 1.65, "output": 8.25, "cached": 0.165},
    "sonnet": {"input": 1.65, "output": 8.25, "cached": 0.165},
    "claude-4-haiku": {"input": 0.4, "output": 2.0, "cached": 0.04},
}


def estimate_tokens(char_len: int) -> int:
    if char_len <= 0:
        return 0
    return max(1, int(math.ceil(char_len / 4)))


def get_model_rates(
    model: str,
    extra_rates: Optional[Dict[str, Dict[str, float]]] = None,
) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """Return (input_rate, output_rate, cached_rate) per 1M tokens."""
    merged = {**MODEL_RATES, **(extra_rates or {})}
    spec = merged.get(model)
    if not isinstance(spec, dict):
        return (None, None, None)
    try:
        return (float(spec["input"]), float(spec["output"]), float(spec["cached"]))
    except Exception:
        return (None, None, None)


def estimate_cost_usd(
    input_tokens: int,
    output_tokens: int,
    cached_input_tokens: int,
    rate_input: Optional[float],
    rate_output: Optional[float],
    rate_cached: Optional[float],
) -> Optional[float]:
    if rate_input is None or rate_output is None or rate_cached is None:
        return None
    billable_in = max(0, int(input_tokens or 0) - int(cached_input_tokens or 0))
    cached_in = max(0, int(cached_input_tokens or 0))
    out = max(0, int(output_tokens or 0))
    return (
        (billable_in / 1_000_000.0) * rate_input
        + (out / 1_000_000.0) * rate_output
        + (cached_in / 1_000_000.0) * rate_cached
    )
