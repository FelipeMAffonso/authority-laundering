# RUBRIC — T5 Training-distribution impossibility for channel-uniform compliance

**Post-hoc rubric, applied to verify the `proof.py` output.** This rubric defines what counts as full credit, partial credit, and failure for the two-grader equivalence verification of Theorem~\ref{thm:impossibility}. The pre-attempt convention is preserved structurally even though the rubric is filed after the proof script.

## Full credit (PASS)

All three of the following hold:

1. **SymPy symbolic step.** The KL-projection FOC $-\rho/q + (1-\rho)/(1-q) = 0$ is solved analytically and returns $q = \rho$ as the unique solution in $(0,1)$. The second derivative at $q = \rho$ simplifies to $1/[\rho(1-\rho)]$, certifying strict convexity. The compliance log-odds factorisation $g(\ell_{h_1} + \lambda) - g(\ell_{h_2} + \lambda)$ is confirmed by symbolic identity.
2. **NumPy numerical witness.** Across at least $32$ sampled $\rho \in (0.05, 0.95)$, the grid-search argmin of the empirical KL is within $10^{-2}$ of $\rho$. Across at least $32$ sampled linear 1-Lipschitz $g$ with $\beta \in (0.3, 1.0)$, the compliance gap satisfies $|g_1 - g_2| \ge \kappa \cdot |\ell_{h_1} - \ell_{h_2}| - 10^{-9}$ at every sample.
3. **Z3 SMT step.** Z3 returns UNSAT on the algebraic FOC $q(1-\rho) = \rho(1-q) \wedge q \neq \rho$ under $\rho, q \in (0,1)$, certifying uniqueness of the projection.

The script must exit `0`.

## Partial credit (PARTIAL)

Either of:

- Exactly two of {SymPy, NumPy, Z3} pass and the third returns `UNKNOWN`, times out, or has a soluble encoding gap with the gap explicitly identified in the script's stdout.
- All three verifiers run, but a NumPy witness lands at margin smaller than the theoretical floor (within tolerance), suggesting the bound is tight rather than violated.

## Failure (FAIL)

Any of:

- A NumPy witness produces $|g_1 - g_2| < \kappa \cdot |\ell_{h_1} - \ell_{h_2}| - 10^{-6}$, a genuine violation of the lower bound.
- Z3 returns `SAT` on the FOC negation, exhibiting a $q \neq \rho$ that satisfies the FOC.
- SymPy fails to recover $q = \rho$ from the FOC, indicating an algebraic error in the theorem statement or the proof.

In any failure case, the SUMMARY.md FAIL marker triggers an investigation of whether the theorem statement, the encoding, or a verifier soundness issue is responsible.
