# RUBRIC — T3 Probing-representation lower bound

**Pre-attempt rubric (written before `proof.py` was run).**

## Full credit (PASS)

All three of the following hold:

1. **SymPy symbolic step.** On the Bernoulli case, the
   expectation-gap representation $(p - q)(\psi(1) - \psi(0))$ is confirmed
   algebraically; the Le Cam identity $\alpha^\star = 1/2 + (1/2)|p - q|$
   produces a residual of zero in `simplify(...)` on the $p \ge q$ branch;
   the Pinsker quantity $D(p, q) := \mathrm{KL}_{\text{Bern}}(p, q) - 2(p - q)^2$
   is shown to satisfy $D(q, q) = 0$ and have non-negative curvature at the
   only point where $D = 0$.

2. **NumPy numerical witness.** Across at least $32$ Bernoulli pairs
   $(p, q) \in (0.05, 0.95)^2$:
   - Pinsker margin (KL $-$ 2 TV$^2$) is non-negative within $10^{-9}$ at
     every sample.
   - Le Cam simulated accuracy with $n_{\text{sim}} \ge 100{,}000$ matches
     the predicted $1/2 + \mathrm{TV}/2$ within $5 \sigma$ ($0.005$).
   - Activation-bridge $|\mathbb{E}_{P_1}[\psi] - \mathbb{E}_{P_2}[\psi]| \le 2 M \mathrm{TV}$
     holds at the saturating $\psi$ (equality witness).
   - A multinomial witness on a $> 2$-point support is included for breadth.
   Random seed `numpy.random.default_rng(42)`.

3. **Z3 SMT step.** Z3 returns UNSAT on the negation of the Le Cam identity
   on Bernoulli (linear arithmetic) and UNSAT on the negation of the
   activation-bridge inequality. SAT on the equality witness. Pinsker is
   outside Z3's decidable theory and is delegated to SymPy + NumPy with the
   scope note in the script's stdout.

The script must exit `0` and write `verification_log.txt`.

## Partial credit (PARTIAL)

Either of:

- Two of {SymPy, NumPy, Z3} pass; the third has a soluble encoding gap
  (e.g., Z3 returns UNKNOWN on the activation bridge in higher dimensions),
  with the gap explicitly identified in stdout.
- Pinsker margin is positive but very small at boundary $p = q$ cases
  (this is consistent with the inequality being tight, not a violation).

## Failure (FAIL)

Any of:

- Pinsker margin negative by more than $10^{-9}$ at any witness.
- Le Cam simulated accuracy differs from predicted by more than $5 \sigma$
  or $0.01$, whichever is larger.
- Z3 SAT on the negation of the Le Cam identity or the activation bridge.
- A multinomial witness violates Pinsker by more than $10^{-9}$.

A failure on Pinsker would be the most consequential: it would indicate the
encoding has confused a constant or that the binary-Bernoulli case has been
extrapolated incorrectly.
