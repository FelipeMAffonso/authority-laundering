# Frontier language models comply with fabricated authority they can identify as fabricated — Reviewer Release

[![arXiv](https://img.shields.io/badge/arXiv-XXXX.XXXXX-b31b1b.svg)](https://arxiv.org/abs/XXXX.XXXXX)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

This folder is the reviewer-facing auditability package for *Frontier language models comply with fabricated authority they can identify as fabricated* (the paper that introduces the *authority laundering* construct). The paper shows that nine frontier closed-weight models across three laboratories operationalize fabricated institutional documents on 31.0 per cent of trials when the fabrication arrives through a tool return and on 1.5 per cent of trials when the identical content arrives as a user imperative, a 20.7-fold ratio that inverts the command-priority ordering enforced by current alignment training. The effect is user-context-invariant: tool-return compliance reaches 26.7 per cent on adversarial-context queries, 33.0 per cent on professional-context queries, and 25.9 per cent on consumer-context queries, which dissociates the channel-as-authority signal from query-framing-cued compliance. Every scenario in every bank carries fabricated institutional content whose acceptance produces real-world harm; the user-context axis varies only how the harmful intent is grammatically packaged in the user turn. The release contains every raw per-trial JSON, every line of code, every scenario definition, every judge prompt, and a single script that recomputes every numerical claim in the paper from the raw data.

## Start here

**Open a terminal in this folder and run:**

```bash
pip install -r requirements.txt
python verify_paper_numbers.py
```

The script prints a PASS/FAIL table covering every pooled rate, per-model rate, per-domain rate, Cohen's h, generational comparison, grounding defense cell, and refusal-floor count claimed in `paper/main_v2.md` (the current manuscript; `paper/main.md` is the superseded v1) and `paper/supplementary_v2.md`. It loads approximately 8,400 complete redacted JSONs under `data/raw/` (closed-9 × 27 scenarios × 5 conditions × 5 reps for the headline plus the 4-model open-weight supplementary panel) and recomputes each claim from scratch. A clean run ends with `TOTAL: 85/85 PASS, 0/85 FAIL` and the message `VERDICT: every paper claim reproduces from raw data.` Runtime is under 2 minutes on a laptop; no network calls.

If you want to see a short-form output, grep the last three lines:

```bash
python verify_paper_numbers.py | tail -n 3
```

For a full claim-to-row audit trail showing which data fields reproduce which paper sentence, see `AUDIT_TRAIL.md`.

## Layout

```
release/
  README.md                 this file
  AUDIT_TRAIL.md            claim-to-raw-field map for every number in the paper
  LICENSE                   MIT
  CHANGELOG.md              version history
  ethics.md                 redaction policy, ToS compliance, canary GUID
  requirements.txt          pinned Python deps
  .env.example              API-key template for replication
  verify_paper_numbers.py   <-- START HERE: recomputes every paper claim
  redact_raw_dump.py        produces the redacted corpus from data/raw/
  export_yaml.py            re-exports scenarios/judge prompts to YAML
  data/
    README.md               JSONL schema reference
    raw/                    8,615 redacted per-trial JSONs (al_*.json)
    channel_prior_probe/    9 closed-weight-model probe outputs (v0.4)
  code/
    experiment/             scenario bank (27 scenarios), conditions, runner, audit scripts
    harness/                2-turn multi-provider harness, judge, cost tracker
    config/                 model registry (no API keys shipped) + .env.example
    validation/             human-validation export script + CSV (60-trial sample)
    run_focused_pilot.py    replicator: 4-condition main factorial
    run_grounded_study.py   replicator: grounding-defense sweep
    probe_channel_priors.py        v0.4 mechanism: channel-prior trichotomous probe
    probe_channel_priors_corpus.py v0.4 mechanism: stimulus corpus for the probe
    run_subject_local.py           v0.4 mechanism: local subject-model harness for activations
    exp1_linear_probe.py           v0.4 mechanism: linear probe on hidden-state representations
    exp2_compliance_correlation.py v0.4 mechanism: probe-direction <-> compliance correlation
    exp3_causal_patching.py        v0.4 mechanism: activation-patching causal test
    extract_matched_pairs.py       v0.4 mechanism: byte-identical (genuine, fabricated) pair extraction
    rejudge_llama_trials.py        v0.4 mechanism: open-weight rejudge for capacity-scaling ablation
    runpod_launch.py               v0.4 mechanism: RunPod A100 launcher
    verify_all.py                  v0.4 mechanism: end-to-end orchestrator
    PROBE_CHANNEL_PRIORS_PROTOCOL.md      v0.4 mechanism: protocol documentation
    METHODOLOGY_AUDIT_VS_NATURE.md        v0.4 mechanism: methodology calibration vs Nature
    EMPIRICAL_RESULTS.md                  v0.4 mechanism: running results aggregation
    MECHANISM_PLAN.md                     v0.4 mechanism: strategic agenda
    MECHANISM_README.md                   v0.4 mechanism: cold-start guide
    MECHANISM_COSTS.md                    v0.4 mechanism: cost tracker
  evaluation/
    README.md               scenarios and judge-prompt structure
    scenarios.yaml          27 scenarios (exported from experiment/scenarios.py)
    judge_prompts.yaml      verbatim coherence/acceptance/harmful_execution rubrics
  paper/
    main.md                 paper main text (Markdown source)
    main_v2.md              v0.4 paper main text rev with theory + mechanism findings
    supplementary.md        supplementary information (Markdown source)
    supplementary_v2.md     v0.4 supplementary information rev
    references.bib          BibTeX bibliography
    main.pdf                rendered paper (build artifact)
    main.docx               rendered paper (build artifact)
    supplementary.pdf       rendered supplementary (build artifact)
    supplementary.docx      rendered supplementary (build artifact)
    build.sh                Pandoc build script
    nature-template.tex     LaTeX template (Nature-style)
    fallback_header.tex     LaTeX header fallback
    figures/                8 PNGs + generate_figures.py + fig1.html source
  theory/                   v0.4 theoretical framework
    bayesian_source_reliability.tex  ~1100-line LaTeX manuscript with 8 theorems and 11 predictions
    refs.bib                32 verified bibliography entries
    build.sh                pdflatex pipeline
    PLAN.md                 strategic agenda for the theoretical loop
    PROGRESS.md             iteration log (iter00 scaffolding, iter01-iter07 attack closures)
    SUMMARY.md              cold-start summary of theorems, predictions, and verifier coverage
    README.md               entry point for theory readers
    proofs/                 one subfolder per theorem T1-T7
      MATHARENA_METHODOLOGY.md  proof-pipeline standard
      RIGOR_CHECKLIST.md        per-node audit form
      SUMMARY.md                T1-T7 verifier coverage matrix
      T1_rate_ratio/      proof.py + NOTES.md + RUBRIC.md + verification_log.txt
      T2_grounding/       same layout
      T3_probing/         same layout
      T4_subgaussian/     same layout
      T5_impossibility/   same layout
      T6_priority_inversion/ same layout
      T7_capacity_bound/  same layout
```

## What is new in v0.4 (2026-05-06)

The v0.4 release adds the theoretical framework and the mechanism-paper auxiliary work that close the loop between the v0.3 behavioural compliance gap and the falsification predictions that motivated the paper. Three additions:

1. **Theoretical framework** under `theory/`. The LaTeX manuscript `bayesian_source_reliability.tex` formalises 8 publication-grade theorems plus 11 falsifiable empirical predictions in a Bayesian source-reliability framework for channel-conditioned compliance. Theorem 1 is the rate-ratio bound under 1-Lipschitz logit-compliance, Corollary 3 is the empirical falsification rule that the channel-prior probe exercises, Theorem 2 is the grounding-effect bound (Sonnet 4.5 backfire is interpreted as sign-violation falsification under Corollary 6), Theorems 3 and 4 are the Pinsker-Le Cam-Kantorovich-Rubinstein lower bound on probe accuracy and its Gaussian sharpening, Theorem 5 is the training-distribution impossibility theorem (Cloud-Theorem-1 analogue), Theorem 6 is the priority-inversion theorem for the regime-conditioned channel coefficient, and Theorem 7 is the capacity-correction theorem to channel-prior emergence. Every theorem ships with a `proof.py` under `theory/proofs/T*/` that passes two-grader equivalence across SymPy, NumPy, and Z3 (T1-T7 verifier coverage matrix in `theory/proofs/SUMMARY.md`). The proof pipeline caught two real bugs in the original drafts: Theorem 4's linear-bound form was REFUTED at every witness configuration, and Theorem 7's sharp-constant form had wrong constants. Both were corrected before shipping.

2. **Channel-prior probe falsification** under `code/probe_channel_priors.py` and `data/channel_prior_probe/`. The trichotomous probe (genuine / partial / fabricated, with 0-100 confidence) was run across all 9 closed-weight subject models on 21 paired (genuine, fabricated) institutional documents covering 13 domains, 4 delivery channels (system, tool, document-paste, user), and 3 replicates per cell, totalling n=2,160 probe trials. The result is unanimous: every model classifies fabricated documents as fabricated on at least 80 per cent of trials and as genuine on 0 per cent of trials, regardless of channel. The pooled empirical channel-prior log-odds gap $\Delta\hat\ell$ is therefore 0.000 on every model. Under Corollary 3, the v0.3 behavioural compliance log-odds gap of $\Delta\hat\gamma = 3.380$ exceeds the channel-prior gap by the full 3.380 log-odds, falsifying rational Bayesian source-weighting unanimously across Anthropic, OpenAI, and Google laboratories. The full per-model narrative sentences and aggregate verdict are in `code/EMPIRICAL_RESULTS.md`.

3. **Mechanism-paper auxiliary infrastructure** under `code/`. The repository now ships the falsification-prediction scripts (`exp1_linear_probe.py` for the probing-representation accuracy floor, `exp2_compliance_correlation.py` for the probe-direction vs compliance correlation, `exp3_causal_patching.py` for activation-patching), the local-subject harness (`run_subject_local.py`), the matched-pair extractor (`extract_matched_pairs.py`), the open-weight rejudge for the capacity-scaling ablation (`rejudge_llama_trials.py`), and the RunPod A100 launcher (`runpod_launch.py`). Protocol documentation lives in `PROBE_CHANNEL_PRIORS_PROTOCOL.md` and `METHODOLOGY_AUDIT_VS_NATURE.md`. The end-to-end orchestrator is `verify_all.py`.

The verification script `verify_paper_numbers.py` continues to report 85/85 PASS against the v0.3 behavioural numbers. A future v0.5 will extend the script with channel-prior probe verdict checks (against `data/channel_prior_probe/*.json`) and theorem-pass status checks (against `theory/proofs/T*/verification_log.txt`); see the v0.4 entry in `CHANGELOG.md` for the planned additions.

## Redaction policy (one paragraph)

Four scenarios carry SEVERE operational harm if the model's output is acted on: HEA_01 (pediatric acetaminophen overdose), HEA_02 (warfarin + NSAID co-administration), SEC_01 (disabling SSL verification), and SEC_02 (SQL string concatenation). For those four scenarios only, the raw per-trial JSONs in `data/raw/` have the dangerous operational payload within model response text replaced with the literal token `[REDACTED dangerous specific]`. All surrounding reasoning, refusal framing, citations, warnings, and judge reasoning remain verbatim. Every meta-field that the PASS/FAIL table depends on is preserved intact: `model_key`, `scenario_id`, `condition`, `judge_harmful_execution`, `judge_coherence`, `judge_acceptance`, `judge_model`, `judge_raw_*`, `input_tokens`, `output_tokens`, `subject_cost_usd`, `elapsed_s`, `timestamp`, `system_prompt`, `turn1_user_message`, `turn2_user_message`, and the full `tool_turn` with its fabricated document. MODERATE and MINOR scenarios are not redacted at all. Redaction applied 3,407 substitutions across 762 trials out of 8,615; the mapping from raw field to redacted release is one-to-one, and the verify script produces identical output against the live raw corpus and the redacted release. Full policy is in `ethics.md`; the redactor is `redact_raw_dump.py` which is shipped in this folder and can be re-run against any copy of the raw pilot.

## Five-minute reproduction recipe

```bash
# 1. Install
python -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. Recompute every paper claim from raw data
python verify_paper_numbers.py

# 3. (optional) Inspect a single trial
python -c "import json; print(json.load(open('data/raw/al_gemini-3.0-flash_HEA_01_acetaminophen_pediatric_TOOL_DIRECT_dharmful_t0_*.json'.replace('*','c20cb75a'))).keys())"

# 4. (optional) Re-run the pilot end-to-end
cd code
cp config/.env.example config/.env    # edit with real API keys
python -X utf8 run_focused_pilot.py   # ~$200, 8-12 hours
python -X utf8 run_grounded_study.py  # ~$25, 2-3 hours
```

Expected output of step 2 (truncated):

```
TOTAL: 85/85 PASS, 0/85 FAIL
VERDICT: every paper claim reproduces from raw data.
```

## Key numbers the paper makes, and where each one lives

| Paper claim | Raw-data query |
|---|---|
| TOOL_DIRECT 31.0% (377/1215) pooled across 27 scenarios | `sum(judge_harmful_execution) / count over condition=='TOOL_DIRECT'` |
| CONTROL_NONE 2.9% (35/1209) baseline | same, `condition=='CONTROL_NONE'` |
| USER_IMPERATIVE 1.5% (18/1200) kill-experiment | same, `condition=='USER_IMPERATIVE'` |
| DOC_USER_PASTE 7.8% (95/1215) | same, `condition=='DOC_USER_PASTE'` |
| TOOL_DIRECT_GROUNDED 28.8% (297/1030) defense | same, `condition=='TOOL_DIRECT_GROUNDED'` |
| User-context-invariant split: adversarial-context 26.7% / professional-context 33.0% / consumer-context 25.9% on TOOL | user-context-bank subset of `condition=='TOOL_DIRECT'` |
| Gemini 3.0 Flash 68.1% on TOOL (92/135) | `model_key=='gemini-3.0-flash', condition=='TOOL_DIRECT'` |
| Gemini 3.1 Flash Lite 47.4% on TOOL (64/135) | `model_key=='gemini-3.1-flash-lite', condition=='TOOL_DIRECT'` |
| GPT-5.4 Nano 41.5% on TOOL (56/135) | `model_key=='gpt-5.4-nano', condition=='TOOL_DIRECT'` |
| Claude Sonnet 4.5 31.9% on TOOL (43/135) | `model_key=='claude-sonnet-4.5', condition=='TOOL_DIRECT'` |
| Claude Haiku 4.5 30.4% on TOOL (41/135) | `model_key=='claude-haiku-4.5', condition=='TOOL_DIRECT'` |
| Claude Opus 4.6 26.7% on TOOL (36/135) | `model_key=='claude-opus-4.6', condition=='TOOL_DIRECT'` |
| GPT-5.4 Mini 17.0% on TOOL (23/135) | `model_key=='gpt-5.4-mini', condition=='TOOL_DIRECT'` |
| Claude Opus 4.7 11.9% on TOOL (16/135) | `model_key=='claude-opus-4.7', condition=='TOOL_DIRECT'` |
| Claude Sonnet 4.6 4.4% on TOOL (6/135) — lowest per-model rate | `model_key=='claude-sonnet-4.6', condition=='TOOL_DIRECT'` |
| Cohen's h: TOOL vs CONTROL = 0.84 | `cohens_h(377/1215, 35/1209)` |
| Cohen's h: TOOL vs USER_IMPERATIVE = 0.94 | `cohens_h(377/1215, 18/1200)` |
| Cohen's h: TOOL vs DOC_USER_PASTE = 0.62 | `cohens_h(377/1215, 95/1215)` |
| 20.7-fold ratio (TOOL / USER_IMPERATIVE) | `(377/1215) / (18/1200) ≈ 20.7` |
| Per-domain TOOL vs CONTROL (15 domains) | aggregated per scenario-domain mapping |
| Sonnet 4.5 backfire under grounding: 31.9% → 35.7% | `model_key=='claude-sonnet-4.5', TOOL_DIRECT vs TOOL_DIRECT_GROUNDED` |
| Gemini 3.0 Flash backfire: 68.1% → 73.0% | `model_key=='gemini-3.0-flash', TOOL_DIRECT vs TOOL_DIRECT_GROUNDED` |
| 8.1x generational hardening (Opus 4.6 vs 4.7) on the harmful-only subset | `16/60 ÷ 2/60 on SEVERE+MOD 12-scenario subset` |
| 2.2x generational hardening on full 27-scenario corpus | `36/135 ÷ 16/135 = 2.25` |
| Wilson 95% CI on TOOL pooled: 28.5% to 33.7% | computed from `377/1215` |
| Open-weight panel TOOL pooled 71.1% (324/456) | reported in supplementary §S12, secondary panel |

Every row above maps to exactly one or two raw-data fields per JSON. The verify script runs the queries in the right column and compares against the value in the left column. See `AUDIT_TRAIL.md` for the full 85-check table.

## Replicating the pilot against live APIs

Reproducing the 5-condition matrix requires API keys for Anthropic, OpenAI, and Google, plus a Python 3.11 environment. Cost estimates below assume the pricing in effect at arXiv v1 (April 2026) and the model IDs in `code/config/models.py`.

```bash
cd code
cp config/.env.example config/.env   # fill in ANTHROPIC_API_KEY, OPENAI_API_KEY, GOOGLE_API_KEY
python -X utf8 run_focused_pilot.py       # 4 conditions x 9 models x 27 scenarios x 5 reps
python -X utf8 run_grounded_study.py      # grounding-defense sweep
```

Per-cell cost: roughly $0.05-0.30 per 60-trial cell depending on provider, with Anthropic Opus costing the most and Gemini Flash Lite the least. Total pilot budget landed near $200-250 for the 5,869-trial closed-weight corpus (the open-weight panel through OpenRouter adds approximately $1). Runtime is bounded by provider rate limits rather than compute, and the full pilot completes in roughly 8-12 wall-clock hours with three-way parallelism.

Model identifiers drift. If a specific version is retired, substitute the closest available successor in `code/config/models.py`. The harness dispatches on the `provider` field, so any OpenAI-compatible chat-completion endpoint (Azure, Together, OpenRouter) plugs in with a base URL override.

## Citation

```bibtex
@misc{affonso2026authoritylaundering,
  author       = {Affonso, Felipe},
  title        = {Authority Laundering in Large Language Models},
  year         = {2026},
  eprint       = {XXXX.XXXXX},
  archivePrefix= {arXiv},
  primaryClass = {cs.CL},
  howpublished = {arXiv:XXXX.XXXXX}
}
```

## License

MIT. See `LICENSE`.

## Ethics

Dangerous specifics within SEVERE-scenario model responses are replaced with `[REDACTED dangerous specific]` tokens in `data/raw/`. Judge scores, harmful-execution labels, and every meta-field used by `verify_paper_numbers.py` are preserved. The unredacted corpus is available to qualified researchers under a Data Use Agreement via the OSF mirror. No coordinated-disclosure embargo gates the release, which matches the release conventions of Betley et al. 2026, Cloud et al. 2026, Greshake et al. 2023, and Debenedetti et al. 2024. Full policy in `ethics.md`.
