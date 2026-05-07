# MathArena Methodology — Step 0 of the Proof Pipeline

**Status:** This is the foundational methodological standard. Every proof node entering the pipeline must satisfy the MathArena rigor criteria before symbolic verification (SymPy / Z3 / Lean / Coq / Alethfeld) is attempted.

**Source:** Petrov, I., Dekoninck, J., Baltadzhiev, L., Drencheva, M., Minchev, K., Balunovic, M., Jovanovic, N., & Vechev, M. (2025). *Proof or Bluff? Evaluating LLMs on the 2025 USA Math Olympiad.* ETH Zurich + INSAIT Sofia. https://files.sri.inf.ethz.ch/matharena/usamo_report.pdf. Companion: https://matharena.ai/

This document codifies their methodology as the entry standard for our proofs.

---

## 1. The MathArena Grading Architecture

The MathArena project evaluated eight state-of-the-art LLMs (Gemini-2.5-Pro, R1, Grok 3, Flash-Thinking, Claude 3.7, QwQ, o1-pro, o3-mini) on the six proof-based problems of the 2025 USAMO. The methodology has four pillars.

### Pillar 1 — Two independent expert graders per proof.

Modeled after the IMO grading process. Each problem was independently scored by two former national IMO team members against a pre-established 7-point rubric. This **double-grading** procedure decreases personal bias and ensures consistency. Disagreements between graders are resolved by discussion, not by averaging.

**Pipeline implication:** every proof node in `proofs/` must be verified by at least **two independent verifiers** drawn from {SymPy symbolic, Z3 SMT, NumPy numerical witness, Lean type-checked, Coq machine-checked, Alethfeld decision-procedure}. Where the verifiers disagree, the disagreement is investigated and reported, not papered over.

### Pillar 2 — Pre-established grading rubric per problem.

For each USAMO problem, the MathArena team developed a standardized 7-point grading scheme drawing from authoritative community resources (Art of Problem Solving forums, USAMO archives). Partial credit is awarded for "significant and meaningful progress." The rubric is published before grading begins.

**Pipeline implication:** every proof node must have a `RUBRIC.md` in its directory specifying what counts as full credit, what counts as partial credit, and what counts as failure. Rubrics are written before the proof is attempted, not after. Examples:
- `proofs/thmA_inversion/RUBRIC.md` should specify: closed-form characterization of inversion threshold (3 pts), proof of non-empty inversion interval (2 pts), genericity claim (open positive measure subset) (2 pts).
- `proofs/derivations/bayesian_b/RUBRIC.md` should specify: closed-form posterior bias (2 pts), positivity proof (2 pts), monotonicity proof (2 pts), recovery of linear special case as Bayesian limit (1 pt).

### Pillar 3 — Mistake categorization.

MathArena's graders categorize every error into one of four classes:

1. **Logic errors:** unjustified reasoning steps, incorrect rationale, misinterpretation of previous progress.
2. **Assumption errors:** introduction of unproven or incorrect assumptions that undermine subsequent steps.
3. **Creativity errors:** fundamentally incorrect solution strategies due to inability to identify the correct approach.
4. **Algebra/Arithmetic errors:** critical algebraic or arithmetic miscalculations.

In their results, **Logic** was the most frequent failure mode across all eight LLMs.

**Pipeline implication:** every PARTIAL or FAIL audit on a proof node must classify the failure into one of these four categories in the NOTES.md `Rigor Audit` section. This forces mechanical honesty about which kind of error occurred and routes the fix to the correct intervention (re-derivation vs re-thinking vs re-computing).

### Pillar 4 — LLM auto-grading is unreliable.

MathArena tested whether LLMs (o3-mini, Claude 3.7) could replace human graders. Result: both models inflated scores by **up to 20×**, awarding points for incorrect or unjustified reasoning. The auto-graders frequently could not distinguish a flawed proof from a correct one.

**Pipeline implication:** an LLM cannot be the verifier of its own work. Every proof node requires verification by **non-LLM** machinery: symbolic algebra (SymPy), satisfiability solving (Z3), proof assistants (Lean, Coq), decision procedures (Alethfeld). LLMs may write the proof but cannot grade it. The numerical witness (`simulate.py`) is verified by direct execution against an analytical claim, not by another model.

---

## 2. The Five Failure Modes MathArena Identified in LLM Proofs

These are the specific patterns I must guard against in every node I produce.

### Failure mode 1: Skipping critical steps as "trivial" or "standard."

MathArena identified this as the dominant failure of o3-mini, the second-best reasoning model on USAMO 2025. The model frequently labeled critical proof steps as "trivial" without justification. Even when the validity of those steps was crucial to the overall argument, they were dismissed.

**Defense:** banned phrases in proof bodies — "trivially," "obviously," "as is well-known," "it is standard that," "by standard arguments." Each such phrase must be replaced with either a one-line in-place argument or an exact citation (paper + theorem number).

### Failure mode 2: Overgeneralization from numerical examples.

Models frequently extrapolated a pattern from small numerical cases to the general claim, without proving the pattern actually holds in generality. **This is fundamentally flawed for proof tasks** (MathArena §4, p. 5).

**Defense:** numerical witnesses (`simulate.py`, parameter-grid sweeps, calibrated examples) are illustration, not proof. Any claim of the form "the result holds across the parameter space" requires an analytical genericity argument: the parameter set on which the claim holds must be characterized as open and of positive Lebesgue measure (or whichever measure is canonical for the parameter space).

### Failure mode 3: Fabricated citations.

MathArena identified this as Gemini-2.5-Pro's most concerning failure mode. The model generated citations to "theorems or lemmas that appear plausible but, to the best of our knowledge, are not real." This was particularly prevalent on hard problems where the model could not produce a correct solution.

**Defense:** every citation must have a corresponding entry in `reference-materials/literature/`, consisting of (i) the PDF (preferably the published version, fallback to NBER/SSRN/arXiv preprint), and (ii) the extracted markdown. Each citation in a proof's NOTES.md must point to a specific theorem or section of the cited source by page number. Citations not backed by an extracted-and-read source are removed.

### Failure mode 4: Same wrong strategy across attempts.

MathArena found that each model often attempted the same (and wrong) solution strategy across all four runs of each problem, failing to explore alternatives. This is a kind of mode collapse on solution space.

**Defense:** when a proof attempt fails, the next attempt must use a *different* strategy. Documenting failed approaches in the NOTES.md `Discovery Log` section is required so subsequent runs (whether by me or by the remote agents) do not repeat the same strategy. Strategies tried and failed are listed explicitly.

### Failure mode 5: Logic errors via unjustified reasoning steps.

MathArena's graders flagged this as the **most frequent** failure mode across all models. Solutions used unjustified reasoning steps, incorrect rationale, or misinterpretation of previous progress.

**Defense:** every step of every proof must have a stated justification immediately following the step (as a parenthetical, a labeled "by," or an explicit one-line argument). The Rigor Audit section enforces this; an "Logic" failure is the most common reason for a node being marked PARTIAL.

---

## 3. Pipeline Step 0: MathArena Audit

The proof pipeline is now ordered as follows. Step 0 runs first; subsequent steps run only on nodes that pass Step 0.

```
Step 0: MathArena audit (this document + RIGOR_CHECKLIST.md)
        — Read the node's NOTES.md
        — Verify the Rigor Audit section is present and all items PASS
        — Verify the rubric (RUBRIC.md) is present and pre-dated
        — Verify all citations have backing files in reference-materials/literature/
        — Tag node as ELIGIBLE for symbolic verification

Step 1: Symbolic verification (SymPy)
        — Run proofs/<node>/proof.py
        — Capture exit status

Step 2: SMT verification (Z3)
        — Run proofs/<node>/z3_check.py if first-order arithmetic
        — Capture sat/unsat

Step 3: Numerical witness (NumPy)
        — Run proofs/<node>/simulate.py
        — Verify witness matches analytical claim within tolerance

Step 4: Type-checked verification (Lean)
        — Run proofs/<node>/Lean.lean if applicable
        — Capture compilation status

Step 5: Machine-checked verification (Coq)
        — Run proofs/<node>/Coq.v if applicable

Step 6: Decision-procedure verification (Alethfeld)
        — Sync via sync_alethfeld.py

Step 7: Aggregation
        — Update result_registry.json with all verifier statuses
        — Re-build proof-map.html
        — Verify two-grader-equivalent (at least 2 verifiers PASS) before marking node PASS
```

Steps 1–7 are the existing pipeline. Step 0 is new and is the entry gate.

---

## 4. What This Means for the Existing Nodes

The nodes I produced before adopting this methodology must now be retroactively audited:

| Node | MathArena audit status | Required action |
|------|------------------------|-----------------|
| `derivations/bayesian_b` | PARTIAL — closed-form derivation present, citations partially verified | Add Rigor Audit section to NOTES.md; complete citation verification (Berk, Esponda-Pouzo, Bohren) |
| `derivations/sigma_ordering` | PARTIAL — uses Blackwell complexity primitive without citing Caplin-Dean / Sims rational-inattention foundation | Add Rigor Audit section; cite Caplin-Dean Theorem 1 and Sims §3 explicitly |
| `derivations/passive_learning` | PARTIAL — bifurcation derived but Jacobian eigenvalue analysis incomplete | Add full Jacobian analysis at all three fixed points; cite Guckenheimer-Holmes for transcritical bifurcation normal form |
| `derivations/gradient_update` | PARTIAL — basin agreement at 92% is numerical witness, not proof | Provide analytical equivalence-of-attractors theorem; cite Cesa-Bianchi-Lugosi for entropy-regularized gradient = Fermi limit |
| `thmA_inversion` | PARTIAL — proof works for linear b case + numerical witness; genericity not analytically established | Re-cast as: closed-form characterization of inversion threshold a^dagger, proof that inversion interval has positive measure for an open subset of parameter space |
| `thmB_externality` | PARTIAL — calibrated magnitudes but strong-set-order theorem not proven from primitives | Add formal proof that E(K) contracts in the strong set order under the c_j primitive |
| `layer_dynamics` | PARTIAL — cascade amplification is first-order Taylor; nonlinear simulation is far outside linear regime | Add explicit linearization theorem with second-order remainder bound; document where linearization breaks down |

Each row corresponds to a TaskCreate I have already opened (#15 acquisition, #17 T1A re-audit, #18 L1.3 Jacobian, #19 cascade error bound).

---

## 5. The Standard Going Forward

No proof node enters the pipeline without:

1. A `RUBRIC.md` written before the proof is attempted.
2. A `NOTES.md` ending with a `Rigor Audit` section (per RIGOR_CHECKLIST.md).
3. All citations verified against extracted-and-read primary sources in `reference-materials/literature/`.
4. Two-grader-equivalent verification (at least two of {SymPy, Z3, NumPy, Lean, Coq, Alethfeld} agreeing).
5. Documented failed strategies in a `Discovery Log` section, so successor runs do not repeat them.

This standard slows the work substantially. That is the point. MathArena's data show that the LLMs which appeared to perform well on numerical-answer benchmarks (AIME, HMMT) collapsed on proof-based ones (USAMO 2025), exactly because the standards differ. The same trap will swallow this paper if I do not hold to the higher standard from the start.

---

## 6. References

- Petrov, I. et al. (2025). *Proof or Bluff? Evaluating LLMs on the 2025 USA Math Olympiad.* ETH Zurich + INSAIT Sofia. PDF stored at `reference-materials/literature/matharena_usamo.pdf`; markdown at `matharena_usamo.md`.
- Balunovic, M. et al. (2025). *MathArena: Evaluating LLMs on Uncontaminated Math Competitions.* arXiv:2505.23281.
- MathArena project home: https://matharena.ai/
- MathArena GitHub: https://github.com/eth-sri/matharena
