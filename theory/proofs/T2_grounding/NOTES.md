# T2 — Grounding-effect bound, signed

## Theorem statement (verbatim from `bayesian_source_reliability.tex`, Theorem 2)

Suppose Assumption 4, Assumption 5, and 1-Lipschitz $g$ on $\mathbb{R}$ hold;
the grounding fact $F$ is conditionally independent of $h$ given $R$; and the
conditional Bayes factor $B(F \mid c, h) = B(F)$ is matched across channels at
the likelihood-ratio level. For a contradicting grounding fact $F$ with
$B(F) > 1$, the channel-conditioned compliance log-odds satisfy

$$
-\log B(F) \;\le\; \operatorname{logit} \gamma(c, h, F) \;-\; \operatorname{logit} \gamma(c, h) \;\le\; 0,
$$

and the magnitude of the (posterior log-odds) reduction is independent of the
channel.

## Restated proof, informal then formal

### Informal sketch

Conditioning on $F$ updates the posterior log-odds by a Bayes-factor term:
$\log[P(F \mid R = 1) / P(F \mid R = 0)] = -\log B(F)$. Because $F$ is
conditionally independent of $h$ given $R$, this update enters additively and
identically across channels. A contradicting $F$ has $B(F) > 1$, hence
$-\log B(F) < 0$, so the posterior log-odds decrease. A monotonic compliance
function $g$ preserves the sign of the input shift, and the 1-Lipschitz
hypothesis bounds the absolute compliance shift by $\log B(F)$. Combined, the
compliance shift lies in $[-\log B(F), 0]$, and is the same magnitude at the
posterior level for any channel.

### Formal proof

Step 1 (posterior update on $F$). Conditional on $F$, by Bayes' rule and the
conditional independence of $F$ from $h$ given $R$,
$$
\mathbb{P}(R = 1 \mid c, h, F) \;=\; \frac{\pi(h) L_r(c) P(F \mid R = 1)}{\pi(h) L_r(c) P(F \mid R = 1) + (1 - \pi(h)) L_u(c) P(F \mid R = 0)}.
$$
Taking the logit and using the same algebra as in T1,
$$
\operatorname{logit} \mathbb{P}(R = 1 \mid c, h, F)
\;=\; \operatorname{logit} \pi(h) + \log[L_r(c)/L_u(c)] - \log B(F),
$$
where $-\log B(F) = \log[P(F \mid R = 1) / P(F \mid R = 0)]$. Justification:
direct algebra; the simplification is verified symbolically in
`proof.py::verify_sympy` by computing the residual against the expected
expression and confirming it is zero.

Step 2 (sign of the posterior shift). For contradicting $F$,
$B(F) := P(F \mid R = 0)/P(F \mid R = 1) > 1$, equivalently
$P(F \mid R = 1) < P(F \mid R = 0)$, so $\log[P(F \mid R = 1)/P(F \mid R = 0)] < 0$.
Hence the posterior log-odds decrease by exactly $\log B(F)$. Justification:
direct from the definition of $B(F)$.

Step 3 (channel invariance of the posterior shift). The posterior shift
$-\log B(F)$ does not depend on $\pi(h)$, hence is the same on every channel.
Justification: substitute any $\pi(h_i) \in (0, 1)$ into Step 1 and the shift
term remains $-\log B(F)$. SymPy confirms by computing the residual of the
shift across two distinct $\pi$ values; the residual is zero.

Step 4 (compliance log-odds bound). The compliance log-odds equals
$g(\operatorname{posterior log-odds})$. The shift in compliance log-odds is
$$
g(\ell - \log B(F)) - g(\ell)
$$
where $\ell$ is the pre-$F$ posterior log-odds. By 1-Lipschitz,
$$
|g(\ell - \log B(F)) - g(\ell)| \;\le\; |\log B(F)| \;=\; \log B(F).
$$
By monotonicity of $g$ (inherited from $f$) and $\log B(F) > 0$,
$g(\ell - \log B(F)) \le g(\ell)$, so the shift is non-positive. Combined,
$$
-\log B(F) \;\le\; g(\ell - \log B(F)) - g(\ell) \;\le\; 0.
$$
Justification: 1-Lipschitz absorbs the magnitude; monotonicity fixes the sign.

Step 5 (channel-invariance of magnitude). The posterior shift
$\ell_{h} - \log B(F) - \ell_{h}$ equals $-\log B(F)$ at every channel (Step 3).
Hence the magnitude of the posterior reduction is exactly $\log B(F)$ on every
channel. The compliance reduction is bounded above by $\log B(F)$ at every
channel (Step 4), with equality whenever $g$ has unit slope on the relevant
segment. Justification: the equality case is realised by the linear-with-slope-1
member of the 1-Lipschitz family, demonstrated by the NumPy clipped-identity
witness in `proof.py`.

## Verification summary

`proof.py` runs three independent verifiers:

- **SymPy symbolic.** Confirms the posterior update on $F$ shifts log-odds by
  exactly $\log[P(F \mid R = 1)/P(F \mid R = 0)] = -\log B(F)$, and confirms
  channel invariance by computing the shift at two distinct $\pi$ values and
  showing the residual is zero. Result: PASS.

- **NumPy numerical witness.** $32$ sampled configurations with
  $\log B(F) \in (0.05, 3]$, $\pi \in (0.05, 0.95)$, three different
  1-Lipschitz $g$ families. Confirms (i) compliance shift in
  $[-\log B(F), 0]$; (ii) sign claim (no positive shifts);
  (iii) channel-invariance of the posterior shift, max absolute difference
  $4.4 \times 10^{-16}$. Result: PASS.

- **Z3 SMT.** Encodes $a$ and $a_F = a - \log B(F)$ with $\log B(F) > 0$,
  monotonicity ($g(a) \ge g(a_F)$) and 1-Lipschitz, asks Z3 to falsify the
  bound. UNSAT. Channel-invariance check: UNSAT on the inequality of posterior
  shifts. Equality witness: SAT. Result: PASS.

## Discovery Log

**2026-05-05, attempt 1.** Initial proof.py builds the posterior decomposition
symbolically and confirms the channel-invariance through SymPy, then runs the
numerical witness with three g families. The Z3 encoding works on the two
evaluation points $a$ and $a_F$ with the Lipschitz/monotonicity envelope. PASS
on all three verifiers on first run. One subtle decision: the theorem asserts
the magnitude is "independent of the channel" — at the COMPLIANCE log-odds
level this is true under linear $g$, but for a general 1-Lipschitz $g$ the
compliance magnitude is bounded by $\log B(F)$ rather than identically equal to
it. The verifier therefore checks channel-invariance at the POSTERIOR level
(which is what the proof actually establishes) and the per-channel BOUND at the
compliance level. The NOTES.md state this distinction explicitly.

## Rigor Audit (against RIGOR_CHECKLIST.md)

A1: PASS — the four substantive conditions of the theorem are listed in the
   Setup of `bayesian_source_reliability.tex` (Bayesian compliance, strong
   matching, 1-Lipschitz $g$, conditional independence of $F$, matched Bayes
   factor at the conditional level) and used exactly as defined.
A2: PASS — quantifier scope explicit; the bound holds for all matched $c$, all
   channels with $\pi(h) \in (0, 1)$, and all contradicting $F$ ($B(F) > 1$).
A3: PASS — Remark on operational scope in the paper handles the partial-
   observation regime, and `proof.py` flags any boundary case.
B1: PASS — every step has explicit justification; no banned phrases.
B2: PASS — analytical decomposition leads, witness illustrates.
B3: PASS — closed-form shift, simulation as sanity check.
B4: N/A — no stability claim.
B5: PASS — bound is universal on the admissible region with $B(F) > 1$.
B6: N/A — no empirical primitive.
C1-C4: PASS — citations limited to the paper itself.
D1: PASS — verifiers used: SymPy, NumPy, Z3.
D2: PASS — Z3 UNSAT on the negation.
D3: PASS — NumPy reports per-witness margin and channel-invariance precision.
D4: PASS — `python proof.py` runs deterministically with seed 42.
E1-E4: PASS — no defensive framing, no banned phrases, hedging discipline observed.
