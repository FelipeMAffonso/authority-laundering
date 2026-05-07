# Mechanism Extension — Cost Breakdown

## Bottom line

The full three-experiment package costs roughly **$20-60** depending on which open-weight model we probe. Cheap relative to the existing project budget ($200-250 spent on the closed-weight subject panel).

## Why Anthropic API and OpenRouter are not the right tools

Activation probing requires reading the model's internal hidden states layer-by-layer, which closed APIs do not expose. The Anthropic, OpenAI, and Google APIs only return tokens. OpenRouter is a router on top of those APIs and inherits the same limitation.

Both are fine for two specific roles in this work:

- **Judge step in Experiment 3.** Re-judging patched completions with the existing Claude Haiku 4.5 judge. Roughly 250 patches × $0.001 per judge call = **~$0.25**. Trivial.
- **Behavioral sanity baseline on Llama 3.x.** Running the 27 scenarios × 5 conditions × 5 replicates on Llama 3.1 8B via OpenRouter as a side check that the behavioral effect replicates on the probing target. Roughly 675 trials × $0.0002 per trial = **~$1-3 on OpenRouter** if we use OpenRouter for this. Optional; the activation-capture run produces the same data as a side product if we are running locally anyway.

Neither use case is a meaningful cost.

## The real cost: GPU compute for activation capture and patching

This is the only meaningful expense. Three options ordered by cost.

### Option 1 — NDIF (free, academic)

The National Deep Inference Facility is a free remote NNsight backend supported by NSF. Researchers apply for access and run NNsight scripts against their cluster. As of late 2025 it supports Llama 3.1 8B, 70B, and 405B, plus Mistral and Gemma.

- **Cost: $0**
- **Lead time: 1-2 weeks for academic application approval**
- **Ergonomics: identical to local NNsight; remote.**
- **Limitation: shared queue may slow individual experiments.**

If the paper timeline allows a 2-week wait for approval, this is the right path. The Spears School affiliation should be sufficient for the academic application.

### Option 2 — RunPod / Lambda Labs / vast.ai (cheap and fast)

Rent a GPU by the hour. Pay for what you use. No application required.

- **Llama 3.1 8B on 1×A100 80GB**: $1.50-2.00/hr × ~10 hours of compute = **~$15-20**
- **Llama 3.3 70B on 2×H100 80GB**: $4-6/hr × ~12 hours = **~$50-70**
- **Llama 4 Scout on 4×H100 80GB**: $8-12/hr × ~12 hours = **~$100-150** (closer to the panel but expensive)

RunPod tends to be cheapest, Lambda has more reliable interconnect for multi-GPU. Both have spot pricing that drops 30-50% if the user is okay with preemption.

### Option 3 — Goodfire Ember (paid, sales-gated)

An interpretability-as-a-service API for selected open-weight models. Exposes activation reading and steering. Pricing is sales-gated and likely starts at a few hundred dollars per month minimum. Skip unless Options 1 and 2 fail.

## Recommended path

**Llama 3.1 8B Instruct on RunPod, ~$20 total**, with a fallback to Llama 3.3 70B on RunPod (~$60) if the behavioral effect does not replicate on 8B cleanly.

Reasons:

1. Llama 3.1 8B is the cheapest model that is well-supported by NNsight and that has clean instruction-following. The behavioral effect should replicate on it.
2. RunPod is fast to spin up. An A100 instance is provisioned in under five minutes; the user's existing project tooling (Python 3.11, pip) ports straight over.
3. The total project cost stays in the $20-60 range, which is a small marginal addition to the existing closed-weight spend.
4. If 8B fails, scaling to 70B is a known step rather than an unknown one.

## Per-step cost breakdown

| Step | Compute | API | Total |
|---|---|---|---|
| Step 1 — Extract matched pairs from existing data | $0 (CPU) | $0 | $0 |
| Step 2 — Stand up Llama 3.1 8B on RunPod | ~$3 (2 hours setup) | $0 | ~$3 |
| Step 3 — Behavioral sanity run on Llama 3.1 8B | ~$5 (3 hours) | ~$0.50 (judge) | ~$5.50 |
| Step 4 — Activation capture on matched pairs | ~$3 (1.5 hours) | $0 | ~$3 |
| Step 5 — Probe training | $0 (local CPU) | $0 | $0 |
| Step 6 — Trial-level correlation | $0 (local CPU) | $0 | $0 |
| Step 7 — Causal patching + re-judge | ~$5 (2.5 hours) | ~$0.25 (judge) | ~$5.25 |
| Step 8 — Figures and writing | $0 | $0 | $0 |
| **Total** | **~$16 RunPod** | **~$0.75 Anthropic** | **~$17** |

Add ~$3-5 buffer for re-runs and debugging. Realistic total: **$20-25 on Llama 3.1 8B.**

If we scale to Llama 3.3 70B because the 8B effect is weak, the compute budget triples (Steps 2, 3, 4, 7 become ~$45 instead of ~$16) and the total lands at **$50-65.**

## What is the cost of NOT doing this

The other Claude was right that the paper without mechanism is workshop-to-NMI grade and the paper with mechanism is PNAS / Nature MI grade. The single-author affiliation already pushes against the prestige axis; the mechanism extension is the lever that compensates. Spending $20-60 to lift the paper one tier of journal is a strong return.

## What the cost is NOT

- It is not Anthropic API costs in any meaningful sense (~$0.25 marginal).
- It is not OpenRouter costs in any meaningful sense (optional ~$1-3 for behavioral baseline).
- It is not data-collection costs because we already have the matched-pair stimuli in `data/raw/`.
- It is not human-rater costs because the judge stays at Claude Haiku 4.5.

The cost is one-time GPU rental for forward passes and patching. Once the activations are saved to disk, the probe training and correlation analyses are local CPU work and free.
