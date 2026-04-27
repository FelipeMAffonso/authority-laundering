"""Model registry for authority-laundering experiment.

7 frontier closed-weight models across 3 labs. Open-weight models (Qwen/Llama)
deferred to Study 6 (mechanistic / v2).

Model IDs mirror the spec-resistance registry format. The authority-laundering
harness looks up keys in this dict; the runner passes model_cfg through to
harness.core.call_model.

Pricing is per 1M tokens (input_$/M, output_$/M). Used by CostTracker for
per-provider budget enforcement.
"""

# ---------------------------------------------------------------------------
# Primary lineup (7 closed-weight, 3 labs)
# ---------------------------------------------------------------------------
ALL_MODELS = {
    # -------- Anthropic — 5 generations/tiers --------
    "claude-opus-4.7":   {"provider": "anthropic",  "model_id": "claude-opus-4-7",              "thinking": False},
    "claude-opus-4.6":   {"provider": "anthropic",  "model_id": "claude-opus-4-6",              "thinking": False},
    "claude-sonnet-4.6": {"provider": "anthropic",  "model_id": "claude-sonnet-4-6",            "thinking": False},
    "claude-sonnet-4.5": {"provider": "anthropic",  "model_id": "claude-sonnet-4-5-20250929",   "thinking": False},
    "claude-haiku-4.5":  {"provider": "anthropic",  "model_id": "claude-haiku-4-5-20251001",    "thinking": False},
    # -------- OpenAI (cheap-mini/nano only per budget) --------
    "gpt-5.4-mini":      {"provider": "openai",     "model_id": "gpt-5.4-mini",                 "thinking": False},
    "gpt-5.4-nano":      {"provider": "openai",     "model_id": "gpt-5.4-nano",                 "thinking": False},
    # -------- Google (flash + flash-lite tiers) --------
    "gemini-3.0-flash":       {"provider": "google", "model_id": "gemini-3-flash-preview",       "thinking": False},
    "gemini-3.1-flash-lite":  {"provider": "google", "model_id": "gemini-3.1-flash-lite-preview","thinking": False},

    # v3 expansion (2026-04-25): cheap-but-smart open-weight + alt-aligned models via OpenRouter.
    # Adds 4 models from different post-training regimes (Chinese RLHF, OpenAI open-weight,
    # Meta open-weight, xAI less-aligned) to broaden the panel beyond closed-weight Anglo flagships.
    "deepseek-v4-flash":      {"provider": "openrouter", "model_id": "deepseek/deepseek-v4-flash",  "thinking": False},
    "gpt-oss-120b":           {"provider": "openrouter", "model_id": "openai/gpt-oss-120b",         "thinking": False},
    "llama-4-scout":          {"provider": "openrouter", "model_id": "meta-llama/llama-4-scout",    "thinking": False},
    "grok-4.1-fast":          {"provider": "openrouter", "model_id": "x-ai/grok-4.1-fast",          "thinking": False},
}

# ---------------------------------------------------------------------------
# Pricing per million tokens
# ---------------------------------------------------------------------------
PRICING = {
    # Anthropic
    "claude-opus-4-7":        (15.00, 75.00),
    "claude-opus-4-6":        (15.00, 75.00),
    "claude-sonnet-4-6":      (3.00,  15.00),
    "claude-haiku-4-5-20251001": (1.00, 5.00),   # judge default
    # OpenAI
    "gpt-5.4-mini":           (0.40,  1.60),
    "gpt-5.4-nano":           (0.10,  0.40),
    "gpt-4.1-mini":           (0.40,  1.60),
    "gpt-4.1-nano":           (0.10,  0.40),
    # Google
    "gemini-3.1-pro-preview": (1.25,  10.00),
    "gemini-3-flash-preview": (0.15,  0.60),
    "gemini-2.5-flash":       (0.15,  0.60),     # judge default
    "gemma-3-27b-it":         (0.04,  0.15),
    # OpenRouter (open-weight + alt-aligned, v3 panel)
    "meta-llama/llama-3.3-70b-instruct":    (0.135,  0.40),
    "qwen/qwen-2.5-72b-instruct":           (0.80,   0.80),
    "deepseek/deepseek-v4-flash":           (0.14,   0.28),
    "openai/gpt-oss-120b":                  (0.039,  0.19),
    "meta-llama/llama-4-scout":             (0.08,   0.30),
    "x-ai/grok-4.1-fast":                   (0.20,   0.50),
}

# ---------------------------------------------------------------------------
# Judge configuration
# ---------------------------------------------------------------------------
# Default judge: cheap, fast, reliable — gemini-2.5-flash or claude-haiku-4.5.
# Pick Haiku 4.5 to stay inside Anthropic's tooling (same stream as production),
# or Gemini 2.5 Flash for lowest cost per call.
JUDGE_MODEL_DEFAULT = "claude-haiku-4.5"

JUDGE_MODELS = {
    "claude-haiku-4.5": {
        "provider": "anthropic",
        "model_id": "claude-haiku-4-5-20251001",
        "thinking": False,
    },
    "gemini-2.5-flash": {
        "provider": "google",
        "model_id": "gemini-2.5-flash",
        "thinking": False,
    },
    "gpt-4.1-nano": {
        "provider": "openai",
        "model_id": "gpt-4.1-nano",
        "thinking": False,
    },
}

# ---------------------------------------------------------------------------
# Analysis groupings
# ---------------------------------------------------------------------------
SCALING_PAIRS = [
    ("claude-opus-4.7", "claude-sonnet-4.6"),
    ("gpt-5.4-mini", "gpt-5.4-nano"),
    # No within-lab scaling for Google (1 model only after dropping 3.1 Pro)
]

GENERATIONAL_PAIRS = [
    ("claude-opus-4.7", "claude-opus-4.6"),
]

LABS = {
    "Anthropic": ["claude-opus-4.7", "claude-opus-4.6", "claude-sonnet-4.6"],
    "OpenAI":    ["gpt-5.4-mini", "gpt-5.4-nano"],
    "Google":    ["gemini-3.0-flash"],
}


def compute_cost(model_id: str, input_tokens: int, output_tokens: int) -> float | None:
    """Compute estimated cost in USD based on token counts."""
    if model_id in PRICING:
        inp, out = PRICING[model_id]
        return (input_tokens * inp + output_tokens * out) / 1_000_000
    return None
