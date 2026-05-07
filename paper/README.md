# paper/ — Authority laundering main paper + supplementary

## Status
Two live versions:
- **v1** (`main.md`, `supplementary.md`): the original PNAS-grade behavioural paper. 9 closed-weight models x 27 scenarios, channel-gradient compliance results, user-grounding defence analysis. Built artifacts (`main.pdf`, `main.docx`, `supplementary.pdf`, `supplementary.docx`) reflect this version.
- **v2** (`main_v2.md`, `supplementary_v2.md`): v1 + a Mechanism section that frames "channel as authority" as a non-Bayesian response, intended for NMI / Nature flagship. `main_v2.md` is the active manuscript. `supplementary_v2.md` is currently a copy of v1 — the new theory / verification / mechanism / predictions / replication appendices still need to be authored and merged.

## File map
| File | Purpose |
|---|---|
| `main.md` | v1 main text (245 lines). Sections: Abstract, Experimental setup, Authority laundering via tool outputs, Channel gradient, Cross-lab generalization, User-grounding defence, Discussion, Methods, Tables 1-2, Refs. |
| `supplementary.md` | v1 supplementary (1285 lines, S1-S13 ending in Ethics). |
| `main_v2.md` | v2 main text (350 lines). Adds a "Mechanism: channel as authority is not a Bayesian source-reliability response" section between user-grounding and related work. |
| `supplementary_v2.md` | v2 supplementary. Currently identical to `supplementary.md` — see the merge note below. |
| `references.bib` | Bibliography (shared across versions). |
| `build.sh` | Pandoc pipeline (md -> pdf + docx) using `nature-template.tex`. |
| `build_arxiv.sh` | Variant pipeline producing the arXiv tarball (`arxiv_submission.zip`, `arxiv/`, `arxiv-template.tex`). |
| `nature-template.tex` | LaTeX template for the Nature-family build. |
| `fallback_header.tex` | Header fragment for fallback PDF builds. |
| `figures/` | All paper figures (PNG + PDF + HTML generators + build scripts). |
| `_drafts/` | Empty staging area for in-progress sections to be merged into `supplementary_v2.md`. |
| `_audit/` | Subagent audit reports: `iter01_math_audit.md`, `iter01_organization_audit.md`. |
| `_archive/` | Prior paper versions and abandoned drafts (`authority_laundering_v1.md`, `authority_laundering_v2.md`, `cognitive_hooks.md`, `mechanism_section_draft.md`, `outline.md`, `supplementary_v1.md`). |
| `_inspect_pages/`, `_page_renders/` | Per-page render artifacts from build inspections. |

## Build
```bash
cd paper
bash build.sh       # main.docx + main.pdf + supplementary.docx + supplementary.pdf
bash build_arxiv.sh # arxiv_submission.zip + arxiv/ tree
```

## Supplementary sections (v1, currently mirrored in v2)
| Section | Purpose |
|---|---|
| S1 | Scenario bank |
| S2 | Fabricated document samples |
| S3 | Condition builders |
| S4 | Judge protocol |
| S5 | Harness technical details |
| S6 | Model details and costs |
| S7 | Complete compliance matrix |
| S8 | Per-domain and per-harm-level breakdown |
| S9 | Grounding-defence details |
| S10 | Scope |
| S11 | Limitations and sensitivity checks |
| S12 | Open-weight panel results |
| S13 | Ethics and data-release protocol |

## Planned supplementary additions for v2
The v2 main text references machinery (Bayesian source-reliability framework, verification matrix, mechanism pipeline, empirical predictions, replication inventory) that needs to land in `supplementary_v2.md` before submission. The intended target shape is:

| Section | Purpose |
|---|---|
| S1-S12 | Inherited from v1 verbatim. |
| S13 | Channel-prior probing protocol + per-model results (NEW — replaces v1 S13's position; ethics section moves to S19). |
| S14 | Bayesian source-reliability framework: theorems and corollaries supporting the non-Bayesian claim in `main_v2.md`. |
| S15 | Verification matrix (SymPy + NumPy + Z3 coverage) for the claims in S14. |
| S16 | Mechanism pipeline methodology. |
| S17 | Empirical predictions catalog. |
| S18 | Replication code and data inventory. |
| S19 | Ethics and data-release protocol (relocated from v1 S13). |

## Workflow to merge drafts into supplementary_v2
1. Author each new section as a standalone file in `_drafts/` (e.g. `s14_theory_framework.md`, `s15_verification.md`, `s16_mechanism.md`, `s17_predictions.md`, `s18_replication.md`, plus a relocated `s19_ethics.md` if pulling from v1 S13).
2. Write each draft as a drop-in: heading at `## SXX. ...` level, no document preamble.
3. Renumber the existing v1 ethics section to S19 inside `supplementary_v2.md`, then insert the new sections in numerical order before it.
4. Re-run `bash build.sh` and skim the rendered PDF for cross-reference breakage (the main text cites these sections by number).

Earlier draft material (mechanism prose, cognitive-hook framing, outline) lives in `_archive/` and can be cannibalised when authoring the new appendices.
