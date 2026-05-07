# theory/ — Bayesian source-reliability theory for authority laundering

## Status

The theory subdirectory contains seven publication-grade theorems with two-grader-equivalence verification, accompanied by seven corollaries that extend the main results to adjacent regimes. Eight attack iterations have been closed during the autonomous loop, with each iteration documented in `attacks/iter<NN>_*.md` and aggregated in `PROGRESS.md`. The final report from the autonomous loop lives in `SUMMARY.md`, and the per-theorem verifier-coverage matrix is consolidated in `proofs/SUMMARY.md`.

## File map

| File | Purpose |
|---|---|
| bayesian_source_reliability.tex | Main theory paper (~1100 lines, 7 theorems + 7 corollaries) |
| refs.bib | 32 verified bibliography entries |
| build.sh | pdflatex compile pipeline |
| PLAN.md | Strategic agenda, theorem-candidate ladder |
| PROGRESS.md | Iteration log, 0-7 |
| SUMMARY.md | Final report from the autonomous loop |
| proofs/MATHARENA_METHODOLOGY.md | Hardwired proof-pipeline standards |
| proofs/RIGOR_CHECKLIST.md | Per-node audit form |
| proofs/SUMMARY.md | Aggregate verifier-coverage matrix |
| proofs/T\<n\>_*/proof.py | Per-theorem SymPy + NumPy + Z3 verification |
| proofs/T\<n\>_*/NOTES.md | Per-theorem natural-language proof + Discovery Log |
| proofs/T\<n\>_*/RUBRIC.md | Pre-attempt rubric |
| attacks/iter\<NN\>_*.md | Subagent reports from the autonomous loop |

## Quick start

```bash
# Verify all 7 theorems
cd theory/proofs
for d in T1_rate_ratio T2_grounding T3_probing T4_subgaussian T5_impossibility T6_priority_inversion T7_capacity_bound; do
  (cd "$d" && python proof.py)
done

# Build the paper
cd theory && bash build.sh
```

## Theorem map

- **Proposition 1**: Channel monotonicity of compliance (sign of effect, requires only Bayesian compliance).
- **Theorem 1**: Rate-ratio bound under 1-Lipschitz logit-compliance.
- **Theorem 2**: Grounding-effect signed bound.
- **Theorem 3**: Probing-representation lower bound (Pinsker-Le Cam-Kantorovich-Rubinstein).
- **Theorem 4**: Gaussian sharpening of T3.
- **Theorem 5**: Training-distribution impossibility (Cloud Theorem 1 analogue).
- **Theorem 6**: Priority inversion via regime-conditioned channel coefficient.
- **Theorem 7**: Capacity-bounded calibration cost.

Per-theorem natural-language proofs and Discovery Logs live in `proofs/T<n>_*/NOTES.md`. Machine-checked verification scripts (SymPy + NumPy + Z3) live in `proofs/T<n>_*/proof.py`. Pre-attempt rubrics live in `proofs/T<n>_*/RUBRIC.md`.

## Attack history

The `attacks/` subdirectory contains 18 subagent reports across 8 iterations of the autonomous loop. Each iteration combines literature search, counterexample probing, and tightness analysis to stress-test a candidate theorem before it is admitted to the main paper. Iterations 1-2 produced T1 (rate-ratio bound), iteration 3 hardened the rule set, iteration 4 produced T5 (training-distribution impossibility), iteration 5 produced T6 (priority inversion), iteration 6 produced T4 (sub-Gaussian sharpening), and iteration 7 produced T7 (capacity-bounded calibration). The full iteration log is in `PROGRESS.md`.

## What's next

The eleven empirical predictions enumerated in §6 of `bayesian_source_reliability.tex` are scheduled for execution. Results will be tracked in `mechanism/EMPIRICAL_RESULTS.md` once data collection begins.
