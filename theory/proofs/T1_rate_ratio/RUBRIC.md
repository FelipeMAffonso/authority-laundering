# RUBRIC — T1 Rate-ratio bound

**Pre-attempt rubric (written before `proof.py` was run).** This rubric defines
what counts as full credit, partial credit, and failure for the
two-grader-equivalence verification of Theorem 1.

## Full credit (PASS)

All three of the following hold:

1. **SymPy symbolic step.** The posterior-logodds factorisation
   $\operatorname{logit} \mathbb{P}(R = 1 \mid c, h) = \operatorname{logit} \pi(h) + \log[L_r(c)/L_u(c)]$
   is confirmed symbolically (residual zero after `simplify(logcombine(...))`),
   and the equality case at $\beta = 1$ for linear $g$ produces a residual of
   zero against $|\ell_1 - \ell_2|$.

2. **NumPy numerical witness.** Across at least $32$ sampled configurations in
   the admissible region $\pi \in (0.05, 0.95)$, $\lambda \in [-3, 3]$, with
   at least three distinct 1-Lipschitz $g$ families exercised, every sample
   satisfies $|\mathrm{LHS}| \le |\mathrm{RHS}| + 10^{-12}$. Equality holds for
   the $\beta = 1$ linear case and for clipped identity outside the clip
   region. Random seed `numpy.random.default_rng(42)`.

3. **Z3 SMT step.** Z3 returns UNSAT when asked whether the bound can be
   violated under the Lipschitz + monotonicity constraints, and SAT for the
   equality witness at a fixed nonzero gap.

The script must also exit `0` and write `verification_log.txt` next to itself.

## Partial credit (PARTIAL)

Either of:

- Exactly two of {SymPy, NumPy, Z3} pass and the third returns `UNKNOWN`,
  times out, or has a soluble encoding gap (with the gap explicitly identified
  in the script's stdout).
- All three verifiers run, but a numerical witness lands at a margin smaller
  than the theoretical floor (within tolerance), indicating the bound is tight
  rather than violated.

In either case, the result is logged with the specific gap and the SUMMARY.md
flag for T1 lists which component is incomplete.

## Failure (FAIL)

Any of:

- A NumPy witness produces $|\mathrm{LHS}| > |\mathrm{RHS}| + 10^{-9}$ (a
  genuine violation, not a tolerance issue).
- Z3 returns `SAT` on the negation of the bound under the stated Lipschitz +
  monotonicity constraints, exhibiting an explicit counter-model.
- SymPy's residual on the posterior decomposition is non-zero, indicating an
  algebraic error in the theorem statement.

In any failure case, the SUMMARY.md FAIL marker triggers an investigation of
whether the theorem statement is wrong, the encoding is wrong, or the
verifier has a soundness issue.
