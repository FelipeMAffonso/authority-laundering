# RUBRIC — T4 Sub-Gaussian sharpening

**Pre-attempt rubric (written before `proof.py` was run).**

## Full credit (PASS)

All three of the following hold for the AS-STATED bound
$\alpha^\star \ge 1/2 + \Delta_{\rm nb}/(4\sigma)$:

1. **SymPy symbolic step.** The Cauchy-Schwarz step
   $|\mathbf{w}^\top(\mu_1 - \mu_2)| \le \|\mathbf{w}\|_2 \cdot \|\mu_1 - \mu_2\|_2$
   is confirmed via perfect-square factorisation (residual is a sum of
   squares). The rank-1 reduction
   $\|\mu_1 - \mu_2\|_2 = |c|$ is confirmed. The Tsybakov 2.6 form is
   confirmed at multiple $z$ values: $\Phi(z/2) - (1/2 + z/4) \ge 0$ for
   $z$ in a non-trivial range.

2. **NumPy numerical witness.** Across at least $5$ sub-Gaussian
   configurations (Gaussian, Rademacher, uniform-bounded), at least
   $10{,}000$ samples per channel, simulated optimal-classifier accuracy
   satisfies $\alpha^\star \ge 1/2 + \Delta_{\rm nb}/(4\sigma)$ within a
   $5\sigma$ sampling tolerance. A $d=32$ rank-1 witness with linear
   read-out and isotropic Gaussian residuals is included.

3. **Z3 SMT step.** Z3 UNSAT on the negation of the Cauchy-Schwarz step
   in dimensions $2, 3, 4$. SAT on the equality witness. The transcendental
   step is documented as outside Z3's decidable theory.

The script must exit `0` and write `verification_log.txt`.

## Partial credit (PARTIAL)

Either of:

- **Foundational PASS, but full theorem fails.** All three verifiers PASS on
  the Cauchy-Schwarz step and rank-1 reduction, but two of three verifiers
  REFUTE the as-stated linear bound. In this case, the gap is investigated
  and a corrected form (Gaussian-equality $\alpha^\star = \Phi(z/2)$ or
  Chernoff $\alpha^\star \ge 1 - (1/2)\exp(-z^2/8)$) is identified. The
  partial credit is documented in NOTES.md with explicit identification of
  the constant error in the citation chain.

- **Two of three verifiers PASS on the full theorem.** The third has a
  soluble encoding gap (e.g., Z3 returns UNKNOWN), with the gap explicitly
  identified.

## Failure (FAIL)

Either of:

- **Foundational steps fail.** Cauchy-Schwarz violated by Z3 (counter-model
  exhibited) or SymPy (non-zero residual on the perfect-square
  factorisation), indicating an algebraic error in the proof.

- **The corrected form also fails.** The Hoeffding/Chernoff bound
  $1 - (1/2)\exp(-z^2/8)$ also fails to hold across the sub-Gaussian
  configurations. In this case the entire reduction to a sub-Gaussian
  representational lower bound is in question, and the theorem and proof
  both need restating.

## Note on outcome

This is the rubric for a theorem the verification process is expected to
discover an issue with. The methodology rule "where verifiers disagree,
investigate the disagreement; do not paper over it" is the operative principle;
PARTIAL with a clear gap diagnosis is the right outcome when the as-stated
bound's constant is wrong.
