# mechanism/ — Activation probing and causal patching for the authority-laundering paper

This folder adds the mechanistic extension required for PNAS / Nature MI submission. It provides three experiments that move the paper from "behavioral observation" to "behavioral observation + linearly-decodable internal representation + causal intervention."

Read `PLAN.md` first for the full scientific design. Read `COSTS.md` for the budget breakdown (TL;DR: ~$20 on RunPod with Llama 3.1 8B). This README is the operating manual.

## Quick start

```bash
# 1. Set up environment (local laptop, no GPU yet).
cd mechanism
pip install -r requirements.txt

# 2. Extract matched (TOOL_DIRECT, USER_IMPERATIVE) pairs from existing data.
python extract_matched_pairs.py
# -> outputs/matched_pairs.jsonl  (one line per pair, ~250-300 pairs)

# 3. Provision RunPod A100 80GB (or use NDIF). Edit config.py if needed.
#    Then on the GPU box:
python run_subject_local.py --model meta-llama/Llama-3.1-8B-Instruct --capture
# -> outputs/activations/<trial_id>.npz  (one file per trial)

# 4. Train layer-by-layer probes (CPU is fine).
python exp1_linear_probe.py
# -> outputs/probes/probe_layer_<L>.pkl
# -> outputs/exp1_results.json  (accuracy table)

# 5. Trial-level compliance correlation (CPU).
python exp2_compliance_correlation.py
# -> outputs/exp2_results.json

# 6. Causal patching at the best layer from Experiment 1 (back on the GPU box).
python exp3_causal_patching.py --layer <best_layer_from_exp1>
# -> outputs/patches/<pair_id>.json
# -> outputs/exp3_results.json

# 7. Generate Figure 8 and Figure 9 for the paper.
python figures/generate_mechanism_figures.py
# -> ../paper/figures/fig8_probing.png
# -> ../paper/figures/fig9_patching.png
```

## What each script does

| Script | Inputs | Outputs | GPU required? |
|---|---|---|---|
| `extract_matched_pairs.py` | `../data/raw/al_*.json` | `outputs/matched_pairs.jsonl` | No |
| `run_subject_local.py` | `outputs/matched_pairs.jsonl` | `outputs/activations/*.npz` and `outputs/llama_trials/*.json` | Yes (one A100 80GB minimum) |
| `exp1_linear_probe.py` | `outputs/activations/*.npz` | `outputs/probes/probe_layer_*.pkl`, `outputs/exp1_results.json` | No |
| `exp2_compliance_correlation.py` | `outputs/probes/*.pkl`, `outputs/llama_trials/*.json` | `outputs/exp2_results.json` | No |
| `exp3_causal_patching.py` | `outputs/probes/*.pkl`, `outputs/matched_pairs.jsonl` | `outputs/patches/*.json`, `outputs/exp3_results.json` | Yes (one A100 80GB minimum) |
| `figures/generate_mechanism_figures.py` | `outputs/exp1_results.json`, `outputs/exp2_results.json`, `outputs/exp3_results.json` | `paper/figures/fig8_*.png`, `paper/figures/fig9_*.png` | No |

## Subject model

Default: `meta-llama/Llama-3.1-8B-Instruct`. Pulled via Hugging Face Hub on first run. Requires a Hugging Face access token in `HF_TOKEN` for gated Llama weights.

If 8B does not show the behavioral effect cleanly, switch the `--model` flag to `meta-llama/Llama-3.3-70B-Instruct` (and resize to 2×H100 80GB). The pipeline is otherwise unchanged.

## Cloud setup (RunPod)

```bash
# On the RunPod box, after provisioning A100 80GB:
git clone <your-repo-url> authority-laundering
cd authority-laundering/mechanism
pip install -r requirements.txt
export HF_TOKEN=<your-hf-token>
export ANTHROPIC_API_KEY=<your-anthropic-key>   # for the judge in exp3
huggingface-cli login --token $HF_TOKEN

# Pre-download Llama 3.1 8B Instruct weights (one-time, ~16 GB)
python -c "from huggingface_hub import snapshot_download; snapshot_download('meta-llama/Llama-3.1-8B-Instruct')"

# Run capture
python run_subject_local.py --capture
```

RunPod billing accumulates per second the box is active; remember to **stop the pod** when not running. Total compute time is roughly 8-10 hours for the full pipeline at 8B.

## Local laptop setup (no GPU)

You can do all the non-GPU work locally:

```bash
# Extract pairs
python extract_matched_pairs.py

# Train probes once activations are downloaded from the GPU box
# (rsync outputs/activations/ from RunPod to local first)
python exp1_linear_probe.py

# Trial-level correlation
python exp2_compliance_correlation.py

# Generate figures
python figures/generate_mechanism_figures.py
```

## Reproducibility

The matched-pairs extraction is deterministic: given the same `data/raw/` snapshot, it produces the same `matched_pairs.jsonl`. The activation capture is deterministic per trial: `torch.manual_seed(42)` and greedy decoding for activation-capture passes. The probe training uses `random_state=42` everywhere. The patching pass also uses greedy decoding so flips are due to the patch, not sampling noise.

The `outputs/` folder is committed to the public release with the redacted patched completions. Activations themselves are too large to commit (roughly 4 GB total) and are released via the same OSF DUA channel as the unredacted raw trials.

## Known constraints

- **Llama 3.1 8B requires HF gated access.** Apply at <https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct> before the first run.
- **NNsight pinned to 0.3.x.** Newer versions may break the patching API; pinned for reproducibility.
- **Tokenizer chat-template handling differs from the closed-API harness.** This file's `build_prompts.py` reconstructs prompts using the Llama-3 chat template, which means the tokenized prompt length differs slightly from what the closed-weight panel saw. The matched-pair stimuli are textually identical; only the chat-template wrapping is provider-specific.

## Integration with the rest of the paper

After all three experiments land, integrate by:

1. Adding `## Mechanism` section to `paper/main.md` between `## User-grounding as a partial and heterogeneous defense` and `## Related work`. Use `paper/_archive/mechanism_section_draft.md` as the prose stub once experiments are run.
2. Adding Figure 8 and Figure 9 to `paper/main.md` figures.
3. Updating the Abstract with one mechanism sentence.
4. Updating Discussion's "Mechanism (open question)" subsection to "Mechanism" with the probing result as the load-bearing evidence.
5. Updating Methods with a "Mechanism subject" subsection.
6. Adding `mechanism/` to the `release/code/` mirror in the public release.
7. Adding the probing-section block to `release/verify_paper_numbers.py` so reviewers can re-verify the mechanism numbers.
