# Mechanism Extension — Three-Experiment Plan

## Goal

Move the paper from "behavioral observation across 9 closed-weight models" to "behavioral observation + linearly-decodable internal representation + causal intervention." This is the addition that takes the paper from workshop / NMI grade to PNAS / NMI grade and removes the single biggest reviewer objection (no mechanism beyond behavioral).

## What we are testing

Whether the channel-as-authority signal we characterize behaviorally is (a) **decodable** from the model's hidden states on matched content, (b) **predictive** of trial-level compliance, and (c) **causally responsible** for compliance via activation patching. The behavioral data alone show the effect exists; the three experiments here tell us where it lives in the model and whether it is the load-bearing variable.

## The three experiments

### Experiment 1 — Linear decodability of channel origin

**Hypothesis.** A linear probe trained on residual-stream activations at the end-of-context position (the last token of the turn-2 user message, position immediately before the model begins generating its response) classifies channel-of-origin (TOOL_DIRECT vs USER_IMPERATIVE) at well above chance, on **identical fabricated content** that varies only in delivery channel.

**Design.**
- Stimuli: 27 scenarios × 5 replicates × 2 conditions (TOOL_DIRECT, USER_IMPERATIVE) = 270 trials per replicate. Pull from existing `data/raw/al_<model>_*.json`. The fabricated content is the same string in both conditions; only the channel envelope (system tool-result message vs user turn) differs.
- Subject: Llama 3.1 8B Instruct (MVP). Scale to Llama 3.3 70B if effect does not show on 8B.
- Activation capture: residual stream at every layer, last-token position of the full conversation up to the start of `response_turn2`. Save as `(num_layers, hidden_dim)` per trial.
- Probe: L2-regularized logistic regression. 60/20/20 train/val/test split, **stratified by scenario** so the probe is held out on unseen content not just unseen replicates.
- Layer sweep: report probe accuracy as a function of layer depth; identify the layer at which channel becomes decodable.
- Generalization control: also report probe accuracy under **leave-one-domain-out** cross-validation, so the probe cannot rely on domain-specific features.

**Expected headline.** Channel origin is decodable at >90% accuracy from layer N onward on identical content, where N is roughly mid-network.

**Falsification.** If accuracy stays at chance across all layers, or only the lexical-context tokens drive the signal, the linear-decoding account fails and we report that instead. Either result is publishable, but the strong claim requires the positive result.

### Experiment 2 — Trial-level correlation with compliance

**Hypothesis.** The probe's continuous score on a TOOL_DIRECT trial predicts whether that specific trial crosses the compliance threshold. This makes the probe load-bearing rather than incidental: the activations that encode "this came through a tool channel" are the same activations that drive operational compliance.

**Design.**
- For each TOOL_DIRECT trial in the test set (~270 × 0.20 = ~54 trials minimum; if N is too low we expand the test fold), extract the layer-N probe logit ("channel-authority score").
- Pair with the existing binary `judge_harmful_execution` label from the trial JSON.
- Report Pearson r and Spearman ρ between probe score and compliance, plus AUC for compliance ≈ score classifier.
- Bootstrap 95% CI over scenario-level resamples (so the CI accounts for between-scenario variance).
- Sanity check: does the probe score predict compliance on USER_IMPERATIVE trials too? If yes, the signal is general. If no, it specifically tracks the tool channel's effect on compliance.

**Expected headline.** Trial-level probe score predicts compliance at AUC > 0.70, providing evidence that the channel-authority direction is the same one that gates compliance.

**Falsification.** AUC ≈ 0.50 means the probe found a channel signal that is not the compliance signal. We would report that the channel is decodable but mechanistically detached from compliance, which would weaken (but not kill) the paper.

### Experiment 3 — Causal intervention via activation patching

**Hypothesis.** Patching the residual stream at layer N from a USER_IMPERATIVE (refusing) trial into the matched TOOL_DIRECT (complying) trial reduces compliance on the patched run. This is the difference between a probing paper and a mechanism paper, because correlation alone does not establish causation.

**Design.**
- Pick the layer L from Experiment 1 where probe accuracy peaks.
- For each (TOOL_DIRECT compliance, USER_IMPERATIVE refusal) pair on the same scenario and replicate index:
  - Forward pass on USER_IMPERATIVE context up to last token of turn-2 user message; capture residual stream at layer L, last token position.
  - Forward pass on TOOL_DIRECT context with patch: replace residual stream at layer L, last token position with the captured USER_IMPERATIVE activation.
  - Continue forward pass and generate the response_turn2 completion.
  - Re-judge the patched completion with the existing `harness/judge.py` (Claude Haiku 4.5 judge).
- Run the reverse direction as control: patch TOOL_DIRECT activation into USER_IMPERATIVE context. If the channel direction is causal, this should *increase* compliance; if not, it stays at floor.
- Report: (i) % of patched TOOL_DIRECT trials that flip from compliance to refusal, (ii) % of patched USER_IMPERATIVE trials that flip from refusal to compliance, (iii) effect size relative to no-patch baseline.

**Expected headline.** Patching reduces TOOL_DIRECT compliance by X percentage points; reverse patching increases USER_IMPERATIVE compliance by Y percentage points. The asymmetry tells us how directional the channel direction is.

**Falsification.** If patching has no effect on compliance, the activations encode channel without driving the behavior, and we report a probing-only result. If patching has a symmetric effect in both directions, the channel direction is bidirectional, which sharpens the mechanism story.

## What changes in the paper

A new section titled "Mechanism" sits between the current "User-grounding as a partial and heterogeneous defense" (§5) and "Related work" (§6). The section runs roughly 800-1200 words and contains:

- Two new figures: Figure 8 (probe accuracy by layer + leave-one-domain-out generalization) and Figure 9 (trial-level probe score vs compliance + causal patching effect sizes).
- A subsection on the linear-decoding result (Experiment 1).
- A subsection on the trial-level correlation (Experiment 2).
- A subsection on the causal patching result (Experiment 3).
- A short caveat that the probing is on Llama 3.1 8B (or 70B if scaled) as a representative open-weight model, with the closed-weight panel results as the behavioral anchor.

The Abstract gains one sentence linking channel origin to internal representation. The Discussion's "Mechanism (open question)" subsection gets rewritten as "Mechanism" with the probing result as the load-bearing evidence and the Bayesian source-reliability formalization as the open thread.

The Methods gains a "Mechanism subject" section documenting Llama 3.1 8B, NNsight version, layer choice, probe hyperparameters, and patching protocol. The Code Availability statement adds `mechanism/` to the repository.

## Stimuli decisions

We pull matched pairs from the existing `data/raw/al_<model>_*.json` files. The fabricated content is identical across TOOL_DIRECT and USER_IMPERATIVE for a given scenario, so the matched-pair structure is already in the data.

For the local model probing, we re-run the same scenarios on Llama 3.1 8B because:

1. The closed-weight panel cannot be probed (no activation access on Anthropic, OpenAI, Google APIs).
2. Llama 4 Scout, which is in our open-weight panel, requires multi-H100 for FP16 inference and is more expensive to iterate on.
3. Llama 3.1 8B is well-supported by NNsight, runs on a single A100, and is the cheapest path to a real probing result.
4. The behavioral effect should replicate on Llama 3.1 8B (instruction-tuned open-weight, similar capability tier to the open-weight panel that already shows the effect at elevated baseline).

The paper documents this as a representative-model choice and notes that the behavioral cross-lab evidence is on the closed-weight panel while the mechanistic evidence is on Llama 3.1 8B.

## Subject panel decision

We add Llama 3.1 8B as a **mechanism subject** rather than a main panel subject. The behavioral panel for the headline rates stays at 9 closed-weight models. The supplementary §S12 open-weight panel keeps its 4 OpenRouter subjects. The mechanism subject is reported in the new Mechanism section and in Methods, with its behavioral 5-condition rates reported as a sanity check that the channel effect replicates on the probing target.

The behavioral sanity check on Llama 3.1 8B costs roughly $5 via OpenRouter or is free as a side product of the activation-capture run.

## Execution sequence

The three experiments stack on each other and should run sequentially.

1. **Extract matched pairs** from existing data/raw. Pure Python, no GPU. Output: `outputs/matched_pairs.jsonl`. Estimated 30 minutes once the script is written.
2. **Stand up Llama 3.1 8B locally** on RunPod or local GPU. NNsight `LanguageModel("meta-llama/Llama-3.1-8B-Instruct")`. Verify forward pass and chat-template handling on one trial. Estimated 2 hours for first-time setup.
3. **Behavioral sanity run** on the 27 scenarios × 5 conditions × 5 replicates = 675 trials, judging with the existing Claude Haiku 4.5 judge. Confirms the channel effect on Llama 3.1 8B. Estimated 2-4 hours.
4. **Activation capture pass** on the matched pairs (~270 trials × 2 conditions). One forward pass per trial, residual stream captured at every layer at the last-token position. Save as `.npz` per trial. Estimated 1-2 hours on A100.
5. **Probe training** on the captured activations. Layer sweep, scenario-stratified split, leave-one-domain-out. CPU only. Output: `outputs/probes/probe_layer_<L>.pkl` and `outputs/exp1_results.json`. Estimated 1 hour.
6. **Trial-level correlation** between probe scores and compliance labels. CPU only. Output: `outputs/exp2_results.json`. Estimated 30 minutes.
7. **Causal patching** on ~250 matched pairs at the best layer from Experiment 1. Two patches per pair (forward and reverse). Re-judge patched completions with Claude Haiku 4.5 at ~$0.25 marginal cost. Output: `outputs/patches/*.json` and `outputs/exp3_results.json`. Estimated 2-3 hours on A100.
8. **Figures and §10 prose** integration into `paper/main.md`. Estimated 1 day of writing.

Total wall-clock: roughly 3-4 weeks part-time at evenings-and-weekends pace, in line with the other Claude's estimate.

## What does not change

- The headline behavioral numbers (31.0 / 7.8 / 1.5 per cent pooled) stay as the lead result. The mechanism is supporting evidence, not a replacement.
- The 27-scenario × 9-model panel stays as the cross-lab generalization result. Adding Llama 3.1 8B does not change the closed-weight headline.
- The user-context cleavage (adversarial / professional / consumer) stays. The mechanism section does not need to redo this contrast on Llama 3.1 8B unless the probing effect varies by user-context, in which case that becomes a third figure panel.
- The Discussion's adversary-taxonomy subsection stays as it is, possibly trimmed per the other Claude's note about it sitting awkwardly in a Nature MI submission.

## Risk register

- **Llama 3.1 8B does not show the behavioral effect cleanly.** Probability: medium. Mitigation: scale to Llama 3.3 70B at roughly 3x the cost (~$60 instead of ~$20).
- **Channel signal is decodable but is not the compliance signal.** Probability: low-medium. Result: probing-only paper, weaker than mechanism-grade but still publishable; report honestly.
- **Causal patching shows no effect.** Probability: low. Result: same as above; report honestly. The probing result alone clears NMI.
- **NNsight version conflicts with current Llama tokenizer / chat-template handling.** Probability: low; the library has been stable on Llama-3.x for over a year. Mitigation: pin NNsight to a known-good version.
- **Compute provider outage during a long capture run.** Probability: low. Mitigation: idempotent per-trial activation capture writes, skip-existing logic in the runner.

## What goes in the public release

`mechanism/` ships into the existing public GitHub repo as a sibling of `harness/`, `experiment/`, etc. The redaction policy applies to any patched completions that reproduce dangerous specifics, and the redaction script extends to cover `outputs/patches/*.json`. The captured activations themselves do not need redaction because they are not human-readable text.

The verification script (`release/verify_paper_numbers.py`) gains a probing-section block that recomputes Experiment 1's headline accuracy and Experiment 3's headline patching effect from the saved outputs, so reviewers can verify the mechanism numbers the same way they verify the behavioral numbers.
