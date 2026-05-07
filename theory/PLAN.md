# theory/ — Bayesian source-reliability theory for authority laundering

## Strategic agenda

The behavioural and mechanism work characterises channel-conditioned compliance empirically. Theory turns this into a Nature-flagship-grade contribution by deriving a quantitative model whose predictions can be falsified, and whose falsification under empirical rates pins down the deviation as a specific non-Bayesian heuristic. The minimum publishable target is two clean theorems with empirical tests; the stretch target is three theorems including a probing-mechanism connection.

## Theorem candidates

| Tier | Theorem | Status | Target output |
|---|---|---|---|
| 1 | Rate-ratio bound under Bayesian compliance | Drafted, proof complete | Empirical falsification at log-odds ratio 3.38 vs prior odds ratio ~5x |
| 1 | Grounding-effect bound | Drafted, proof complete | Predicted channel-invariance falsified by Sonnet-4.5 backfire |
| 2 | Probing-representation lower bound | Drafted, proof sketched | Connects mechanism (probe accuracy) to theory (non-Bayesian gap) |
| 3 | Cross-lab convergence under shared training-distribution prior | Open | Quantifies cross-lab concordance under population Bayesian model |
| 3 | Killer "must-occur" theorem analogous to Cloud Theorem 1 | Open | Single gradient step on channel-tagged data installs channel prior regardless of distribution |
| 3 | No-free-lunch tradeoff between rational source-weighting and helpfulness | Open | Helpful assistant must violate Bayesian channel-weighting on at least one channel |

## What the proof pipeline does

`/proof-pipeline` reads `bayesian_source_reliability.tex`, parses theorem environments, and runs verification on each proof. It identifies gaps, sketches improvements, and updates the LaTeX in place. Run periodically (every 3 iterations) and after major theorem additions.

## What the loop does

The loop iterates autonomously. Each iteration picks the highest-priority open attack from `PROGRESS.md`, spawns Opus subagents in parallel to attack the move, integrates findings into `bayesian_source_reliability.tex`, updates `PROGRESS.md`, and schedules the next wakeup. Self-paced via `ScheduleWakeup`.

## Stop conditions

- 3 publication-grade theorems with verified proofs and testable predictions.
- 12 iterations without substantive progress.
- `/proof-pipeline` reports all current theorems verified clean and no open attacks remain.

## Rules

- Do NOT touch `paper/main.md` or `paper/supplementary.md`. Theory work lives in `theory/` only.
- Theorem statements must be testable against the existing `data/raw/` corpus or against the mechanism activations in `mechanism/outputs/`.
- Proof sketches must be complete enough to flag specific assumptions; "TODO" markers are acceptable for first drafts but must be resolved before the theorem is marked publication-grade.
- Every theorem statement gets a corresponding empirical-test specification in §5 of the LaTeX paper.
- Cross-references to existing literature (Sperber 2010, Tversky 1974, Wallace 2024) are required for the framing.
- LaTeX must compile cleanly under `pdflatex` (or `xelatex` if Unicode characters appear). The build script in `theory/build.sh` is the canonical compile path.

## Build

```bash
cd theory
bash build.sh
# -> bayesian_source_reliability.pdf
```

## Files

- `bayesian_source_reliability.tex` — main paper with model, theorems, proofs, predictions, discussion.
- `refs.bib` — bibliography.
- `build.sh` — compile to PDF.
- `PROGRESS.md` — running log of loop iterations and the open-attack queue.
- `attacks/` — subagent attack reports, one file per attack.
