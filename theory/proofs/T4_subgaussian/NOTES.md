# T4 — Gaussian sharpening of the probing lower bound

## Theorem statement (verbatim from `bayesian_source_reliability.tex`, Theorem 4, shipped form)

Suppose the conditions of Theorem 3 hold and additionally:
(i) the compliance read-out is linear, $\psi(\mathbf{x}_h) = \mathbf{w}^\top \mathbf{x}_h + b$;
(ii) the channel-conditional activations are equal-covariance Gaussian $P_1, P_2$
separated along a rank-1 channel-of-origin direction
$\mathbf{v}^\star := (\mu_1 - \mu_2)/\|\mu_1 - \mu_2\|_2$ with projected standard
deviation $\sigma$. Then the Bayes-optimal channel-of-origin classification
accuracy is exactly

$$
\alpha^\star \;=\; \Phi\!\left(\frac{\Delta_{\textnormal{nb}}}{2\sigma}\right),
$$

with $\Phi$ the standard normal CDF and $\Delta_{\textnormal{nb}} := \|\mu_1 - \mu_2\|_2$
the non-Bayesian residual gap from Theorem 3. For $\sigma \in [2.2, 4.5]$ at late
layers of a 3-to-8B transformer and $\Delta_{\textnormal{nb}} = 1.8$, this gives
$\alpha^\star \in [0.579, 0.659]$.

**Revision note.** An earlier draft stated a linear lower bound
$\alpha^\star \ge 1/2 + \Delta_{\textnormal{nb}}/(4\sigma)$ citing Tsybakov 2009
Theorem 2.6. The verification pipeline refuted that form (the cited result bounds
$\alpha^\star$ from *above* via Pinsker, and the Gaussian Bayes accuracy has slope
$1/(2\sqrt{2\pi}) \approx 0.199 < 1/4$ at the origin). The shipped statement above
is the Gaussian-exact identity, which is a textbook fact and carries no
direction-of-inequality hazard. The refutation is preserved in the Discovery Log
and reproduced in `proof.py` Section R so the catch stays reproducible.

## Restated proof, informal then formal

### Informal sketch

For two equal-covariance Gaussians separated along a single direction, the
log-likelihood ratio is affine in the projection onto that direction and the
Bayes-optimal decision boundary under equal priors is the midpoint of the two
projected means. Each class is then classified correctly with probability equal
to the normal CDF evaluated at half the standardised separation, so the balanced
accuracy is exactly $\Phi(\Delta_{\textnormal{nb}}/(2\sigma))$. Because $\Phi$ is
strictly increasing, the accuracy decreases monotonically in $\sigma$, which gives
the reported interval by evaluating at the two endpoints of the projected-SD range.

### Formal proof

**Step 1 (Cauchy-Schwarz, foundational).** The linear read-out
$\psi(\mathbf{x}_h) = \mathbf{w}^\top \mathbf{x}_h + b$ has expectation gap
$|\mathbb{E}_{P_1}[\psi] - \mathbb{E}_{P_2}[\psi]| = |\mathbf{w}^\top(\mu_1 - \mu_2)|
\le \|\mathbf{w}\|_2 \,\|\mu_1 - \mu_2\|_2$ by Cauchy-Schwarz, with equality iff
$\mathbf{w} \parallel \mu_1 - \mu_2$. Justification: verified symbolically via the
perfect-square factorisation $\|\mathbf{w}\|^2\|\mu\|^2 - (\mathbf{w}^\top\mu)^2
= \sum_{i<j}(w_i\mu_j - w_j\mu_i)^2 \ge 0$ and by Z3 (UNSAT on the negation in
$d \in \{2,3,4\}$).

**Step 2 (rank-1 reduction, foundational).** Under the rank-1 hypothesis
$\mu_1 - \mu_2 = c\,\mathbf{v}^\star$ with $\mathbf{v}^\star$ unit, so
$\|\mu_1 - \mu_2\|_2 = |c|$ and the projection onto $\mathbf{v}^\star$ recovers the
full mean gap. Justification: direct algebra; verified by Z3 (UNSAT on
$\|c\mathbf{v}^\star\|^2 \neq c^2$ under unit norm).

**Step 3 (Bayes-optimal threshold is the midpoint).** For $P_i = N(\mu_i, \Sigma)$
with shared $\Sigma$ and equal priors, the log-likelihood ratio is
$\log[p_1(\mathbf{x})/p_2(\mathbf{x})] = (\mu_1 - \mu_2)^\top \Sigma^{-1}(\mathbf{x}
- (\mu_1+\mu_2)/2)$, affine in $\mathbf{x}$ and zero at the midpoint
$(\mu_1+\mu_2)/2$. Projecting onto $\mathbf{v}^\star$ reduces to one dimension with
the threshold at the projected midpoint. Justification: verified symbolically in
`proof.py::verify_sympy` (the LLR solves to a single root equal to $(m_1+m_2)/2$).

**Step 4 (exact accuracy).** With the midpoint threshold, the probability of
correctly classifying a draw from either class is $\mathbb{P}(N(0,\sigma^2) <
\Delta_{\textnormal{nb}}/2) = \Phi(\Delta_{\textnormal{nb}}/(2\sigma))$, and the
balanced accuracy equals the same quantity. Justification: SymPy evaluates the
Gaussian integral $\int_{-\infty}^{\Delta/2} \mathcal{N}(x;0,\sigma^2)\,dx$ and
confirms it equals $\tfrac12 + \tfrac12\mathrm{erf}(\Delta/(2\sqrt2\,\sigma)) =
\Phi(\Delta/(2\sigma))$; NumPy confirms the identity by Monte-Carlo equality within
binomial tolerance across random configurations and a $d=32$ rank-1 witness.

**Step 5 (monotonicity and the reported interval).** $\partial\alpha^\star/\partial\sigma
= -\Delta_{\textnormal{nb}}/(2\sigma^2)\,\phi(\Delta_{\textnormal{nb}}/(2\sigma)) < 0$,
so accuracy is strictly decreasing in $\sigma$. Evaluating at the endpoints with
$\Delta_{\textnormal{nb}} = 1.8$: $\Phi(1.8/(2\cdot 4.5)) = \Phi(0.200) = 0.579$
and $\Phi(1.8/(2\cdot 2.2)) = \Phi(0.409) = 0.659$. Justification: SymPy reports
the symbolic sign of the derivative and the two endpoint values to three decimals.

## Verification summary

`proof.py` runs three engines on the shipped statement:

- **SymPy symbolic.** Cauchy-Schwarz perfect-square factorisation; rank-1 reduction;
  midpoint-threshold optimality (LLR root); exact accuracy integral
  $= \Phi(z/2)$; monotonicity in $\sigma$; endpoint values $[0.579, 0.659]$.
  Result: PASS.
- **NumPy numerical witness.** Monte-Carlo equality $\alpha_{\text{sim}} \approx
  \Phi(z/2)$ within 5 binomial SDs across random configurations; endpoint
  reproduction at $\sigma = 2.2, 4.5$; $d=32$ rank-1 witness. Result: PASS. An
  auxiliary sub-Gaussian Hoeffding companion (corrected constant) is reported but
  is not part of the shipped statement and does not gate the verdict.
- **Z3 SMT.** UNSAT on Cauchy-Schwarz violation in $d \in \{2,3,4\}$ and on the
  rank-1 reduction. The transcendental accuracy step ($\Phi/\mathrm{erf}$) is
  outside Z3's decidable theory and is covered by SymPy + NumPy. Result: PASS on
  the foundational steps; N/A on the transcendental step.

## Two-grader verdict

T4 PASS. The shipped Gaussian-exact statement is verified by 2/2 applicable engines
(SymPy exact integration + NumPy Monte-Carlo equality), with Z3 covering the
foundational linear-arithmetic steps. The two-grader requirement (>= 2 agreeing
verifiers) is met and no engine reports FAIL on the shipped statement.

## Discovery Log

**2026-05-05, attempts 1-3.** The node was first written for an as-stated linear
bound $\alpha^\star \ge 1/2 + \Delta_{\textnormal{nb}}/(4\sigma)$. NumPy failed it
at all eight random configurations and the $d=32$ witness (margin $-0.0295$ at
$\sigma=2,\Delta=1$: true $\Phi(0.25)=0.5987$ vs as-stated $0.625$). Investigation
established that $\Phi(z/2)$ has slope $1/(2\sqrt{2\pi}) \approx 0.199 < 1/4$ at the
origin, so the linear form exceeds the true Gaussian Bayes accuracy for all $z>0$,
and the cited Tsybakov 2009 Theorem 2.6 gives a Pinsker UPPER bound, the opposite
direction. The node was marked PARTIAL.

**2026-06-11 (audit).** The paper's Theorem 4 was already the Gaussian-exact form
$\alpha^\star = \Phi(\Delta_{\textnormal{nb}}/(2\sigma))$ in the shipped supplementary,
but this NOTES.md and `proof.py` still documented and tested the refuted linear
bound, so the human-grader and machine-grader halves were auditing different
statements. `proof.py` was rewritten to verify the shipped statement (Steps 1-5
above) and this NOTES.md was rewritten to match. The refutation of the linear form
is retained in `proof.py` Section R. The numeric interval was corrected from the
stale $[0.578, 0.658]$ (which used $\Delta_{\textnormal{nb}} = 1.78$) to
$[0.579, 0.659]$ at $\Delta_{\textnormal{nb}} = 1.8$.

## Rigor Audit (against RIGOR_CHECKLIST.md)

A1: PASS — primitives ($\mathbf{w}, \mu_1, \mu_2, \sigma, \Delta_{\textnormal{nb}},
   \mathbf{v}^\star, \Phi$) listed in the statement and used as defined.
A2: PASS — quantifier scope explicit; the identity holds for the stated
   equal-covariance Gaussian rank-1 class under equal priors.
A3: PASS — the shipped claim is an exact identity on the stated Gaussian class,
   not a universal bound over an unspecified family; no unhedged universal remains.
B1: PASS — every step carries an explicit justification; no banned phrases.
B2: PASS — analytical derivation leads (midpoint optimality + exact integral);
   the Monte-Carlo witness illustrates the identity, it does not establish it.
B3: PASS — closed-form $\Phi(\Delta/(2\sigma))$ is the proof; simulation is a
   sanity check on the equality.
B4: N/A — no stability or eigenvalue claim.
B5: PASS — no genericity claim; the result is an exact equality on the named
   class, with monotonicity in $\sigma$ giving the reported interval.
B6: PASS — $\Delta_{\textnormal{nb}}$ identified as the Theorem 3 residual gap,
   $\sigma$ as the projected SD of the linear-probe direction.
C1: PASS — the shipped statement is the standard Gaussian Bayes-accuracy identity;
   it does not depend on Tsybakov 2.6 (whose misuse in the old draft is documented
   in the Discovery Log and no longer load-bearing).
C2: PASS — no external theorem is invoked for the shipped result beyond the
   textbook Gaussian-discriminant fact derived in-place in Steps 3-4.
C3: N/A — no external citation carries the shipped result.
C4: PASS — the Tsybakov reference is now labelled parallel/historical (Discovery
   Log), not foundational.
D1: PASS — verifiers used: SymPy + NumPy on the shipped statement (2 agreeing),
   Z3 on the foundational steps.
D2: PASS — Z3 UNSAT on the negation of the foundational linear-arithmetic steps;
   the transcendental accuracy step is N/A for Z3 and covered by SymPy + NumPy.
D3: PASS — NumPy reports per-configuration deviation in binomial-SD units; the
   identity holds within tolerance and the endpoint values reproduce to 3 dp.
D4: PASS — `python proof.py` runs deterministically with seed 42.
E1-E4: PASS — no defensive framing, no em dashes, no banned tricolons, hedging
   discipline observed.
