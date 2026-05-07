# Rigor Checklist for Proof Pipeline

**Source of standards:** MathArena (Petrov, Dekoninck, Baltadzhiev, Drencheva, Minchev, Balunovic, Jovanovic, Vechev — *Proof or Bluff? Evaluating LLMs on 2025 USA Math Olympiad*, ETH Zurich + INSAIT, May 2025) plus Econometrica editorial standards on identification, genericity, and explicit assumption tracking.

Every node in `proofs/` must satisfy every item below before being marked **PASS**. A node that fails any item is marked **PARTIAL** (with the failing item listed) until the gap is closed.

---

## Section A — Statement Discipline

**A1. Explicit assumption ledger.** The theorem statement (or a numbered Definition immediately preceding it) lists every primitive: which objects are observable, which are derived from named primitives, which are imposed (with justification). No "for tractability" or "we assume" without a citation or a derivation.

**A2. Quantifier transparency.** "There exists" vs "for all" is explicit at every step. Open vs closed sets, strict vs weak inequalities, generic vs measure-zero — distinguished.

**A3. No unhedged universals.** A claim of the form "the bifurcation occurs at X" must specify the set of parameters for which X is the bifurcation point; the set of parameters for which the system is in the bifurcation regime; and what happens outside that set.

---

## Section B — Proof Discipline

**B1. No skipped steps as "trivial" or "standard".** MathArena identified this as the top failure mode of o3-mini, the second-best reasoning model on USAMO 2025. Every "standard" or "trivial" claim must be tagged with a source: an exact lemma reference (with its page number) or a one-line on-the-spot proof. The phrases "it is standard that," "trivially," "obviously," and "as is well-known" are all banned in proof bodies.

**B2. No overgeneralization from numerical examples.** A simulation showing the inversion exists at 63% of grid cells does NOT prove the inversion is generic. The numerical witness is illustration; the proof is analytical (closed-form characterization of the inversion threshold) plus a genericity statement (open-positive-measure parameter set). MathArena identified pattern-overgeneralization as a fundamental flaw for proof tasks.

**B3. Closed-form first, simulation second.** Numerical results may motivate, illustrate, or sanity-check a proof, but a proof body that ends with "as the simulation confirms" is incomplete. Where a closed form is intractable, the proof must explicitly identify what the obstruction is (e.g., "the posterior is intractable in non-conjugate cases; we work the Gaussian-conjugate special case and document robustness numerically").

**B4. Full Jacobian / eigenvalue analysis for stability claims.** Stability of fixed points cannot be argued from utility-comparison heuristics alone. Required: 2x2 Jacobian computed at each fixed point, eigenvalue signs verified under the relevant parameter assumptions, classification (stable / saddle / unstable / Hopf) stated explicitly. For bifurcations, the named bifurcation type (transcritical, saddle-node, pitchfork, Hopf) must be identified with the standard normal form (e.g., Guckenheimer-Holmes Chapter 3).

**B5. Genericity claims require explicit measure arguments.** "The inversion holds generically" requires: (a) statement of the parameter space, (b) statement of the measure (Lebesgue on R^k or otherwise), (c) proof that the inversion-holding subset is open and has positive measure. Calling something "generic" without this is rejected.

**B6. Identification arguments for empirical primitives.** Where the model uses an empirical primitive (the c_j Blackwell complexities, the noise variance σ_η²(K), the prior bias δ_prior), a paragraph must address how it is identified from data: what observables pin it down, what additional assumptions are needed, what variation in the data is required.

---

## Section C — Citation Discipline

**C1. Every citation verified against the primary source.** No citing from memory. No paraphrasing without checking. MathArena identified citation fabrication ("non-existent references") as Gemini-2.5-Pro's most concerning failure mode. Each citation must have a corresponding markdown file in `reference-materials/literature/<name>.md` (PDF + extracted text) and a NOTE in this directory documenting the specific theorem/result being cited and its location in the source (page or section).

**C2. Cite the specific result, not the paper.** A citation to "Bohren 2016" alone is insufficient. The form must be "Bohren 2016 Theorem 1" or "Bohren 2016 Section 4.2." The cited result must support the claim as stated; if it supports a weaker claim, the writing must be weakened.

**C3. Author + year + journal + (best) page number.** Inline citations follow LaTeX biblatex conventions; the bibliography must include DOI or stable URL, plus the explicit pages cited.

**C4. Distinguish citing for foundations vs citing for parallels.** Citations are of two kinds: (i) the result is foundational (we use it directly in the proof), or (ii) the result is parallel (we mention for context but do not depend on). Every citation must be labeled in the NOTES file with which kind it is.

---

## Section D — Verification Discipline

**D1. Two-grader equivalent.** Every proof node passes verification on at least two independent verifiers from {SymPy symbolic, Z3 SMT, NumPy numerical witness, Lean type-checked, Coq machine-checked, Alethfeld decision-procedure}. The verifiers must agree. Disagreement triggers re-examination, not selective reporting.

**D2. Counter-model search.** Where the claim is universal, the verifier must run a counter-model search at sufficient depth. If Z3 returns SAT on the negation, the claim is wrong as stated. (Z3's UNSAT on the negation is the verification.)

**D3. Sensitivity reporting.** Numerical witnesses must include sensitivity analysis: how does the witness change as the calibration moves? If the witness is fragile (large change in result for small change in parameters), the underlying analytical result is suspect.

**D4. Reproducibility.** Every script must run from a fresh checkout with one command and produce the documented output. Random seeds fixed. Dependencies documented.

---

## Section E — Style Discipline (CLAUDE.md interaction)

**E1. No "we now address," "in response to," "the referee suggested," "as noted by the reviewer."** Defensive framing exposes the revision history; the paper must read as if written correctly from the start.

**E2. No em-dashes; no rule-of-three; no asyndetic tricolon; no parataxis.** Banned per CLAUDE.md.

**E3. Hedging discipline.** Verbs: "shows," "provides evidence," "is consistent with," "indicates" for own results. "Proves," "demonstrates," "establishes," "confirms" reserved for cited prior literature, factorial designs that rule out confounds, and TOST equivalence tests. No "definitively."

**E4. No skipping difficulty.** A passage that sweeps over the hard step in the proof ("the rest is computation," "the algebra is standard") is a warning sign. Either spell it out or cite the result.

---

## Section F — Per-Node Audit Form

For each node in `proofs/` (each `derivations/<name>/` and each `thm*/`), the NOTES.md must contain a section titled **Rigor Audit** with the form:

```
## Rigor Audit (against RIGOR_CHECKLIST.md)

A1: PASS / PARTIAL: <gap>
A2: PASS / PARTIAL
A3: PASS / PARTIAL
B1: PASS / PARTIAL
B2: PASS / PARTIAL
B3: PASS / PARTIAL
B4: PASS / PARTIAL: <e.g., "Jacobian computed at active-choosing equilibrium; saddle equilibrium pending">
B5: PASS / PARTIAL
B6: PASS / PARTIAL
C1: PASS / PARTIAL
C2: PASS / PARTIAL
C3: PASS / PARTIAL
C4: PASS / PARTIAL
D1: PASS — verifiers used: <list>
D2: PASS / PARTIAL
D3: PASS / PARTIAL
D4: PASS / PARTIAL
E1-E4: PASS / PARTIAL
```

A node graduates from PARTIAL to PASS only when all entries are PASS. The proof-map.html visualization will be updated to colour-code by audit status.

---

## Section G — When This Checklist Is Insufficient

If the underlying mathematical claim cannot be proven to this standard, the right action is to weaken the claim, not to weaken the standard. Specifically:

- If a closed form is unavailable, state the result as "There exists a non-empty set of parameters such that..." and prove existence rather than full characterization.
- If genericity cannot be established, restate as "Under the calibration..." and own the special-case nature.
- If the Jacobian is intractable, state stability as conjecture supported by simulation rather than as theorem.
- If a primitive cannot be identified from data, label it explicitly as a structural assumption that requires future calibration work.

The honest weak claim is always preferable to the over-strong claim that fails the checklist.
