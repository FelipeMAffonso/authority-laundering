# Replicate the pilot

This guide walks through reproducing the five-condition matrix (CONTROL_NONE, USER_IMPERATIVE, DOC_USER_PASTE, TOOL_DIRECT, TOOL_DIRECT_GROUNDED) across 9 models and 27 scenarios. Expected total spend lands near $200-250 in API costs and 6-10 wall-clock hours with three-way parallelism. Runners live in `release/code/`.

## 0. Verify first, replicate second

Before spending on new API calls, confirm the release corpus reproduces the paper:

```bash
cd release
pip install -r requirements.txt
python verify_paper_numbers.py
```

The verification script runs offline against `data/raw/`, prints a 85-check PASS/FAIL table, and exits 0 on a clean run.

## 1. Environment setup

```bash
cd release/code
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r ../requirements.txt
```

Python 3.11 is the development target. Python 3.10 works if you pin `openai<1.70`. Python 3.9 is not supported because the harness uses `dict[str, Any]` syntax.

## 2. API keys

Copy `config/.env.example` to `config/.env` and fill in the three provider keys. The harness loads the file from `config/.env` at import time. All three keys are required to run the full pilot because the matrix covers nine models across Anthropic, OpenAI, and Google. Running only one provider is supported by editing the `MODELS` list in the runner scripts.

```bash
cp config/.env.example config/.env
# edit config/.env and set ANTHROPIC_API_KEY, OPENAI_API_KEY, GOOGLE_API_KEY
```

## 3. Replicate the main factorial

```bash
python -X utf8 run_focused_pilot.py
```

This runs 9 models times 27 scenarios times 5 replicates times 4 conditions (CONTROL_NONE, USER_IMPERATIVE, DOC_USER_PASTE, TOOL_DIRECT) for 4,860 subject trials plus an equal number of judge calls. Per-trial JSONs land in `data/raw/al_*.json`. Expected runtime is roughly 8-12 hours at the default three-way parallelism, dominated by Anthropic rate limits on Opus tiers. Expected cost is $180-220 at the pricing in effect at arXiv v1.

## 4. Replicate the grounding defense sweep

```bash
python -X utf8 run_grounded_study.py
```

This runs ten scenarios times nine models times five reps times two conditions (TOOL_DIRECT baseline and TOOL_DIRECT_GROUNDED) for 900 additional subject trials. The TOOL_DIRECT cell overlaps with the main pilot, so in practice you can skip re-running it by editing the script to only launch the GROUNDED arm. Expected runtime is 2-3 hours and cost is $20-30.

## 5. Re-verify after re-running

```bash
cd ..
python verify_paper_numbers.py --raw-dir code/data/raw
```

New cell sizes will differ at the margin because API latency and rate-limits cause a small fraction of trials to drop. Point-estimates on the 9-model panel should agree with the paper to within the Wilson CI widths reported in Table 1.

## Runtime and cost estimates by provider

| Provider | Per-call latency | Per-cell cost (60 trials) | Bottleneck |
|---|---|---|---|
| Anthropic (Opus) | 8-20 s | $0.20-0.30 | Organization RPM limit |
| Anthropic (Sonnet / Haiku) | 3-8 s | $0.05-0.12 | Rare |
| OpenAI (GPT-5.4 mini/nano) | 2-6 s | $0.03-0.08 | Rare |
| Google (Gemini 3.0 / 3.1) | 5-15 s | $0.02-0.06 | Thinking-mode warmup |

## Substituting model IDs

Model identifiers drift across releases. If a specific version is retired, substitute the closest successor in `code/config/models.py`. The harness dispatches on the `provider` field rather than the string, so any OpenAI-compatible chat-completion endpoint (Azure, Together, OpenRouter) plugs into the `openai` branch with a base URL override. The `openrouter` branch is already wired for open-weight models and can be pointed at Llama, Qwen, or Gemma builds once credit is loaded.

When substituting a smaller model, expect the compliance pattern to shift: the paper's finding is that the effect is larger in smaller and older models (Gemini 3.0 Flash 70%, GPT-5.4 Nano 48%, Gemini 3.1 Flash Lite 52%), and smaller within-lab successors typically track those rates rather than the flagship-tier 5-15% band.

## Sanity checks before a full run

```bash
cd release/code
python -m experiment.audit_scenarios            # validates stimulus structure
python -X utf8 -m experiment.runner \           # one-rep smoke test
  --model=claude-haiku-4.5 --study=pilot
```

The audit script verifies that every scenario carries the required fields, that harm levels are one of SEVERE / MODERATE / MINOR, and that no prohibited-token content has slipped into the stimulus bank. A smoke test run finishes in under two minutes and costs less than $0.05.
