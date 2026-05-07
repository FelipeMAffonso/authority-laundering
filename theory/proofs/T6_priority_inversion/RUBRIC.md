# RUBRIC — T6 Priority inversion via regime-conditioned channel coefficient

**Post-hoc rubric, applied to verify the `proof.py` output.** This rubric defines what counts as full credit, partial credit, and failure for the two-grader equivalence verification of Theorem~\ref{thm:priority-inversion}.

## Full credit (PASS)

All three of the following hold:

1. **SymPy symbolic step.** The per-regime KL-projection FOC returns $q_\tau = \rho_\tau(h)$ as the unique minimiser on $(0,1)$ for both $\tau \in \{\text{cmd}, \text{dec}\}$. The linear factorisation $\beta_\tau \phi(h) + \alpha_\tau + \lambda(c)$ is confirmed by symbolic identity, with the compliance gap reducing to $\beta_\tau \cdot (\phi(h_{\text{user}}) - \phi(h_{\text{tool}}))$ in each regime.
2. **NumPy numerical witness.** Across at least $32$ sampled corpus configurations satisfying $\rho_{\text{cmd}}(\text{user}) > \rho_{\text{cmd}}(\text{tool})$ and $\rho_{\text{dec}}(\text{tool}) > \rho_{\text{dec}}(\text{user})$, the empirical product $\beta_{\text{cmd}} \cdot \beta_{\text{dec}}$ is strictly negative at every sample. Random seed `numpy.random.default_rng(42)`.
3. **Z3 SMT step.** Z3 returns UNSAT on the negation $\beta_{\text{cmd}} \cdot \beta_{\text{dec}} \ge 0$ under the corpus orderings, certifying the sign-product claim follows from the orderings on $\rho_\tau$.

The script must exit `0`.

## Partial credit (PARTIAL)

Either of:

- Exactly two of {SymPy, NumPy, Z3} pass and the third returns `UNKNOWN`, times out, or has an encoding gap explicitly identified in the script's stdout.
- All three verifiers run, but a NumPy witness lands at a product within $10^{-6}$ of zero, indicating the inversion is qualitatively correct but quantitatively tight at boundary corpus configurations.

## Failure (FAIL)

Any of:

- A NumPy witness produces $\beta_{\text{cmd}} \cdot \beta_{\text{dec}} > 0$, a genuine sign-product violation.
- Z3 returns `SAT` on the negation, exhibiting an explicit $\beta_\tau$ pair that satisfies the corpus orderings yet has the same sign.
- SymPy fails to recover the linear-factorisation identity, indicating an algebraic error in the partition assumption or the proof.

In any failure case, the SUMMARY.md FAIL marker triggers an investigation of whether the partition hypothesis is too strong for the underlying empirical regime.
