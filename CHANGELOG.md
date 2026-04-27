# Changelog

## v0.3 (2026-04-25)

Headline expansion to the closed-9 x 27-scenario corpus. The original 14-scenario adversarial-context bank is joined by 7 professional-context scenarios (journalist verifying CDC press release, pharmacist verifying interaction profile, compliance officer verifying SEC no-action letter, teacher verifying curriculum standard, mental-health counsellor verifying clinical protocol, immigration paralegal verifying USCIS memorandum, registered investment adviser verifying tax-advantaged-account rule) and 6 consumer-context scenarios (parent on baby rash, pet owner on canine ibuprofen, traveller on visa requirement, adult child on elderly polypharmacy, voter on state voter-identification rule, tenant on eviction procedure). Every scenario in every bank carries fabricated institutional content whose acceptance would produce real-world harm; the user-context axis varies only how the harmful intent is grammatically packaged in the user turn. The closed-9 panel collects 6,075 nominal trials across 5 conditions x 5 replicates, of which 5,869 reach a non-null judge label.

The pooled tool-return compliance rate rises from the 14-scenario v0.2 figure of 26.7 per cent to the 27-scenario headline figure of 31.0 per cent, with Cohen's h of 0.84 against the matched baseline. The user-context-invariant cleavage shows that the channel effect operates regardless of user-query framing: tool-return compliance is 26.7 per cent on the adversarial-context subset, 33.0 per cent on the professional-context subset, and 25.9 per cent on the consumer-context subset.

A four-model open-weight panel through OpenRouter (DeepSeek V4 Flash, GPT-OSS-120B, Llama 4 Scout, Grok 4.1 Fast) is added on the same 27-scenario corpus and reported in supplementary S12 as a secondary analysis, with the explicit caveat that the elevated baseline rates blur the channel-isolation contrast on which the closed-weight headline depends.

The verification script `release/verify_paper_numbers.py` now reports 85/85 PASS against the 27-scenario headline AND the 14-scenario harmful-subset sub-claims.

## v0.2 (2026-04-24)

DOC_SMUGGLED to DOC_USER_PASTE rebuild. The original DOC_SMUGGLED condition pasted a compressed presupposition shell rather than the literal full fabricated document, and the v2 collection rebuilds it with the full document text. The v1 raw data is preserved under `data/raw_archived_doc_smuggled/` for provenance. 120 stale TOOL_DIRECT trials from before the v3 stimulus refresh were re-collected, with v0 data archived at `data/raw_stale_v0/`. The verification script reports 65/65 PASS against the v2 numbers.

## v0.1 (2026-04-23)

Initial pilot release accompanying arXiv v0 of *Authority Laundering in Large Language Models*. The release covers 2,891 subject trials across nine closed-weight frontier models (five Anthropic, two OpenAI, two Google), fourteen scenarios across eight domains, five conditions (CONTROL_NONE, USER_IMPERATIVE, DOC_SMUGGLED, TOOL_DIRECT, TOOL_DIRECT_GROUNDED), and five replicates per cell. Judge scoring ran on Claude Haiku 4.5 using the three-dimension rubric exported to `evaluation/judge_prompts.yaml`. SEVERE-scenario response text is redacted in the public JSONL; see `ethics.md` for the full policy.

## v1.0 (planned)

Accompanies the peer-reviewed publication. Adds the four pre-registered robustness checks (alternate-judge cross-validation with Opus 4.7, human-validation subsample, temperature sensitivity sweep at 0.0 / 0.3 / 0.7 / 1.0, and the leave-one-out scenario check that already passes at the v0.3 release at 1.80pp max shift versus the 3.0pp threshold). Adds the bidirectional (benign-direction) arm. Provides unredacted HuggingFace mirrors under a credentialed-access dataset card.
