# RUBRIC — T7 Capacity correction to channel-prior emergence

**Post-hoc rubric, applied to verify the `proof.py` output.** This rubric defines what counts as full credit, partial credit, and failure for the two-grader equivalence verification of Theorem~\ref{thm:capacity}. Z3 is declared N/A on this node because the bound $C \log(C/N) / N$ relies on transcendentals and covering numbers outside Z3's decidable nonlinear-arithmetic theory, so the two-grader pair is SymPy + NumPy.

## Full credit (PASS)

Both of the following hold:

1. **SymPy symbolic step.** The bound $C \log(C/N) / N$ is computed and its limit as $N \to \infty$ for fixed $C$ recovers zero, confirming the order-of-magnitude scaling. The structural unavailability of $\kappa = 0$ is confirmed by computing $\inf g'$ on the logistic family $g(\ell) = \sigma(\beta \ell + \alpha)$ and recovering $\beta > 0$ for any positive $\beta$.
2. **NumPy numerical witness.** Across at least $8$ logarithmically spaced capacity levels $C \in [10^0, 10^3]$, the empirical $L^2$ error of the bounded-capacity channel-prior estimator against the true $\rho$ is monotone-decreasing in $C$ (within a tolerance of $10^{-2}$ to absorb finite-sample noise). Random seed `numpy.random.default_rng(42)`.

The script must exit `0` and explicitly declare Z3 N/A with a one-line statement of the obstruction.

## Partial credit (PARTIAL)

Either of:

- Exactly one of {SymPy, NumPy} passes and the other returns `UNKNOWN`, times out, or has a soluble encoding gap with the gap explicitly identified in the script's stdout.
- Both verifiers run, but the NumPy $L^2$ error sequence has a single non-monotone violation within tolerance, indicating the order-of-magnitude scaling holds with finite-sample noise rather than asymptotically.

## Failure (FAIL)

Any of:

- The NumPy $L^2$ error sequence is monotone-increasing in $C$ across multiple capacity levels, contradicting the convergence claim.
- SymPy fails to recover $\lim C \log(C/N) / N = 0$ as $N \to \infty$, indicating an algebraic error in the bound form.
- The structural argument on the logistic family fails to certify $\inf g' > 0$, indicating an error in the structural unavailability of $\kappa = 0$.

In any failure case, the SUMMARY.md FAIL marker triggers an investigation of whether the order-of-magnitude scaling, the constant $c_1$ identification, or the structural unavailability claim is responsible.
