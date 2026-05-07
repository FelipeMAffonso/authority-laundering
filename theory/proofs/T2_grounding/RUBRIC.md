# RUBRIC — T2 Grounding-effect bound

**Pre-attempt rubric (written before `proof.py` was run).**

## Full credit (PASS)

All three of the following hold:

1. **SymPy symbolic step.** The posterior update on conditioning on $F$ is
   confirmed to shift the posterior log-odds by exactly
   $\log[P(F \mid R = 1)/P(F \mid R = 0)] = -\log B(F)$, residual zero in
   `simplify(logcombine(...))`. Channel-invariance is confirmed by computing
   the shift at two distinct $\pi$ values and showing the residual is zero.

2. **NumPy numerical witness.** Across at least $32$ configurations with
   $\log B(F) > 0$, $\pi \in (0.05, 0.95)$, three distinct 1-Lipschitz $g$
   families, every sample satisfies (i) compliance log-odds shift in
   $[-\log B(F), 0]$ within $10^{-12}$, (ii) shift is non-positive, (iii)
   posterior-level shift is identical across channels within $10^{-12}$.
   Random seed `numpy.random.default_rng(42)`.

3. **Z3 SMT step.** Z3 returns UNSAT on the negation of the bound under
   the Lipschitz + monotonicity + $\log B(F) > 0$ constraints, UNSAT on
   the negation of channel-invariance at the posterior level, and SAT on
   the equality witness $g(a_F) - g(a) = -\log B(F)$.

The script must exit `0` and write `verification_log.txt`.

## Partial credit (PARTIAL)

Either of:

- Two of {SymPy, NumPy, Z3} pass; the third returns `UNKNOWN` or has a soluble
  encoding gap (with the gap explicitly identified in stdout).
- A bound holds at the posterior level but not at the compliance level under
  some $g$ family; this is acceptable provided the gap is identified and tied
  to the linear-vs-1-Lipschitz distinction in NOTES.md.

## Failure (FAIL)

Any of:

- A NumPy witness produces a positive compliance shift (sign violation), or a
  shift outside $[-\log B(F), 0]$ by more than $10^{-9}$.
- Z3 SAT on the negation of the bound (counter-model exhibited).
- SymPy non-zero residual on the posterior update or the channel-invariance
  computation.
- Posterior-level channel invariance fails (max abs shift difference exceeds
  $10^{-9}$).

A failure on the sign claim is the most consequential: it would indicate that
the theorem statement allows for contradicting $F$ to *increase* compliance
under the stated assumptions, which would falsify the theorem.
