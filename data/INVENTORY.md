# data/ inventory

## Trial-JSON corpus (data/raw/)

Total trials: **8,615**

Filename grammar: `al_<model_key>_<scenario_id>_<condition>_<direction>_t<replicate_idx>_<sha8>.json`

The `<sha8>` suffix is an 8-character hash that disambiguates re-runs (e.g. when a trial was re-executed with an updated harness or judge). The five replicate indices `t0`-`t4` give 5 reps per cell. Two ancillary directories under `data/` carry deprecated runs that have been superseded but kept for provenance: `data/raw_archived_doc_smuggled/` (630 files from the original DOC_SMUGGLED compressed-presupposition variant before it was rebuilt as DOC_USER_PASTE) and `data/raw_stale_v0/` (120 stale TOOL_DIRECT trials from before the scenarios.py refresh).

### Models (14 in the directory; 13 in the production lineup)

The CLAUDE.md production lineup is **13 models** across 5 labs. A 14th model key, `gemma-3-27b`, appears in `data/raw/` with only 20 trials (4 scenarios x 5 reps, TOOL_DIRECT x dharmful only) and is a discarded pilot, not part of the published corpus.

| Lab | Model key | Trials | Notes |
|---|---|---|---|
| Anthropic | claude-haiku-4.5 | 655 | Closed-weight |
| Anthropic | claude-sonnet-4.5 | 655 | Closed-weight |
| Anthropic | claude-sonnet-4.6 | 655 | Closed-weight |
| Anthropic | claude-opus-4.6 | 655 | Closed-weight |
| Anthropic | claude-opus-4.7 | 655 | Closed-weight |
| OpenAI | gpt-5.4-mini | 655 | Closed-weight |
| OpenAI | gpt-5.4-nano | 655 | Closed-weight |
| Google | gemini-3.0-flash | 655 | Closed-weight |
| Google | gemini-3.1-flash-lite | 655 | Closed-weight |
| DeepSeek (via OpenRouter) | deepseek-v4-flash | 675 | Open-weight |
| OpenAI (via OpenRouter) | gpt-oss-120b | 675 | Open-weight |
| Meta (via OpenRouter) | llama-4-scout | 675 | Open-weight |
| xAI (via OpenRouter) | grok-4.1-fast | 675 | Open-weight |
| Google (pilot) | gemma-3-27b | 20 | Discarded pilot, not in headline analysis |

Closed-weight models have 655 trials each (135 in each of CONTROL_NONE / USER_IMPERATIVE / DOC_USER_PASTE / TOOL_DIRECT, plus 115 in TOOL_DIRECT_GROUNDED). Open-weight models have 675 (135 in each of all five conditions, including the GROUNDED cell).

### Scenarios (27)

Scenarios span 14 domain prefixes covering the 13 substantive content domains in CLAUDE.md (HEA, SEC, TAX, ENV, LAW, HR, ELC, ACA, MED-journalism = JOURN, COMP, EDU = TEACH, MED-VET = CONS_PET, TRAVEL = CONS_TRAVEL, HOUSING = CONS_TENANT, plus FIN, LEG, MED, PHARM, CONS_ELDER, CONS_PARENT, CONS_VOTER as the 14-bank harmful sub-banks).

| Domain | Scenario IDs |
|---|---|
| HEA (health) | HEA_01_acetaminophen_pediatric, HEA_02_warfarin_nsaid, HEA_03_mmr_efficacy_misinformation |
| SEC (web security) | SEC_01_disable_ssl_verification, SEC_02_sql_string_concat |
| TAX (tax) | TAX_01_401k_home_modernization_hardship, TAX_02_PRETEXT_accredited_investor |
| ENV (environment) | ENV_01_epa_wotus_hobby_landowner, ENV_02_energy_star_override |
| LAW (law) | LAW_01_smithfield_carrington_precedent, LAW_04_PRETEXT_paralegal_emergency_motion |
| HR (HR / hiring) | HR_01_age_cohort_screening |
| ELC (elections) | ELC_01_florida_felon_voting_lfo |
| ACA (academic) | ACA_01_fabricated_meta_analysis |
| JOURN (journalism, MED-journalism in CLAUDE.md) | JOURN_01_cdc_mmr_effectiveness_press_release |
| COMP (compliance / privacy) | COMP_01_edpb_pseudonymized_health_data_scoping |
| TEACH (education / EDU in CLAUDE.md) | TEACH_01_learning_styles_meta_analysis |
| MED (clinical guideline / DSM) | MED_01_dsm_vi_self_managed_benzo_titration |
| PHARM (pediatric pharmacy) | PHARM_01_aap_pediatric_alternation_protocol |
| FIN (finance, SEC regulation) | FIN_01_sec_reg_d_no_action_letter |
| LEG (immigration legal) | LEG_01_uscis_asylum_eligibility_withdrawal |
| CONS_ELDER (consumer-elder) | CONS_ELDER_01_beers_criteria_polypharmacy |
| CONS_PARENT (consumer-parent) | CONS_PARENT_01_infant_fever_rash_decision_aid |
| CONS_PET (consumer-veterinary, MED-VET in CLAUDE.md) | CONS_PET_01_avma_canine_ibuprofen |
| CONS_TENANT (consumer-housing, HOUSING in CLAUDE.md) | CONS_TENANT_01_hud_illinois_5day_notice |
| CONS_TRAVEL (consumer-travel, TRAVEL in CLAUDE.md) | CONS_TRAVEL_01_state_dept_vietnam_visa_advisory |
| CONS_VOTER (consumer-voter) | CONS_VOTER_01_texas_voter_id_expired_license |

### Conditions (5)

- `CONTROL_NONE`: matched baseline, no fabrication (1,755 trials)
- `USER_IMPERATIVE`: fabricated content as direct user instruction (1,755 trials)
- `DOC_USER_PASTE`: fabricated content as user-pasted document (1,755 trials)
- `TOOL_DIRECT`: fabricated content via tool-result message (1,775 trials)
- `TOOL_DIRECT_GROUNDED`: TOOL_DIRECT plus user states contradicting fact (1,575 trials)

### Directions (1 in corpus, 2 planned)

- `dharmful`: fabricated content with harmful operationalisation. **All 8,615 corpus trials are dharmful.**
- `dbenign`: fabricated content with benign operationalisation. **No `dbenign` files are present in `data/raw/`.** The "benign" axis in the published corpus is operationalised at the *scenario* level (the v3 7-scenario benign-professional bank and v4 6-scenario benign-consumer bank ship as scenarios with `direction = harmful` because they still produce real-world harm if accepted; the user-context axis varies how the harmful intent is grammatically packaged, not whether the underlying content is harmful). The `dbenign` slot in the filename grammar is therefore reserved but unused, and the headline analyses do not partition on direction.

## Per-trial schema

A trial JSON has: `trial_id`, `model_key`, `model_id`, `provider`, `scenario_id`, `domain`, `is_pretext`, `condition`, `direction`, `trial_idx`, `system_prompt`, `turn1_user_message`, `turn2_user_message`, `tool_turn` (or `null`), `response_turn1`, `response_turn2`, `tool_invoked`, `input_tokens`, `output_tokens`, `subject_cost_usd`, `elapsed_s`, `timestamp`, `raw_response`, `judge_coherence`, `judge_acceptance`, `judge_harmful_execution`, `judge_model`, `judge_raw_coherence`, `judge_raw_acceptance`, `judge_raw_harmful_execution`.

## Aggregate counts (cell x model x condition x direction)

The closed-weight panel (9 models) is balanced at 135 trials per (model x non-grounded condition) cell and 115 trials per (model x TOOL_DIRECT_GROUNDED) cell, all under `direction = dharmful`. The open-weight panel (4 models) is balanced at 135 trials per cell across all five conditions. The cell size of 135 reflects 27 scenarios x 5 replicates. The 115 figure on the closed-weight GROUNDED cell reflects scenarios where grounding was non-applicable. Per-model totals are 655 closed / 675 open. Closed-weight contribution: 5,895 trials (of these, 5,869 carry a non-null judge label and form the analyzed closed-weight panel reported in the paper; the 26-file difference is null-label records, excluded from every analysis). Open-weight contribution: 2,700 trials. Pilot gemma row: 20 trials. Total: 8,615.

## Project-root cleanup (top 5 recommendations)

1. **Move root-level launchers to `scripts/`.** Eight `run_*.py` files plus `rerun_stale_tool.py` and `build_unredacted_bundle.py` sit at the project root: `run_focused_pilot.py`, `run_consumer_scenarios.py`, `run_doc_user_paste.py`, `run_grounded_study.py`, `run_new_models.py`, `run_new_scenarios.py`, `run_shuffled_all13.py`, `rerun_stale_tool.py`, `build_unredacted_bundle.py`. These are one-shot launchers, not library code, and they crowd the root view. Action: `mkdir scripts/ && git mv run_*.py rerun_stale_tool.py build_unredacted_bundle.py scripts/`. Update any references in `_loop/*.log` headers and `release/README.md` after the move.

2. **Vestigial `preregistration/` folder.** Per CLAUDE.md the AsPredicted preregistration was dropped on 2026-04-25 (item 10 in "Open TODOs for next session"), and the paper does not claim a prereg. The folder still contains `aspredicted_draft.md`. Action: either `git rm -r preregistration/` or move to `_archive/preregistration/` to preserve the historical draft without implying it is live.

3. **Build scratch in `paper/figures/`.** Both `paper/figures/__pycache__/` and `paper/figures/_inspect_pages/` are build/inspection scratch and should not be tracked. The same applies to `mechanism/__pycache__/` and the project-root `__pycache__/`. Action: append `**/__pycache__/`, `paper/figures/_inspect_pages/`, and `mechanism/_pdf_screenshots/` to `.gitignore`, then `git rm -r --cached` the currently tracked instances.

4. **`_loop/` at project root needs a one-line README.** The folder holds session-artefact audits, reanalysis logs, style benchmarks, and case studies (40+ files). Per CLAUDE.md the contents are referenced as supplementary anchors (e.g. `_loop/adversary_case_studies.md` for the Discussion taxonomy block), so the folder should be kept, but a fresh contributor cannot tell its purpose from the name. Action: write `_loop/README.md` with a one-paragraph description (session-artefact archive: audit logs, reanalysis runs, style benchmarks, case studies; pointers to the load-bearing files).

5. **`mechanism/outputs/` subdirectory READMEs.** The mechanism module writes to six output subdirectories (`channel_priors/`, `activations/`, `probes/`, `patches/`, `llama_trials/`, `figures/`) but only the parent has a README. Each subdir's purpose, file naming, and downstream consumers should be documented inline so the activation-probing collaboration hook (Hook 1 in CLAUDE.md's collaboration table) is reproducible. Action: add a one-paragraph `README.md` in each of the six subdirectories.
