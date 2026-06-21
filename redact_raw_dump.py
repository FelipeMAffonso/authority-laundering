"""redact_raw_dump.py — produce the reviewer-facing redacted raw corpus.

Reads `data/raw/al_*.json` (the live pilot corpus), applies the narrow
redaction policy documented in `release/ethics.md`, and writes the redacted
per-trial JSONs to `release/data/raw/`.

Redaction policy (ethics.md §3, "Public-release redaction policy"):

  - SEVERE scenarios only: HEA_01 (pediatric acetaminophen), HEA_02
    (warfarin/NSAID interaction), SEC_01 (SSL verification disable), SEC_02
    (SQL string concatenation).
  - Within SEVERE trials, redact only specific dangerous operational payloads
    that appear in the MODEL RESPONSE text (response_turn1, response_turn2,
    raw_response). Specific patterns:
      - Pediatric dosing: strings like "780 mg" / "24.4 mL" / "60 mg/kg
        every 4 hours" / hour-by-hour schedules.
      - Warfarin/NSAID: multi-day ibuprofen-with-warfarin schedules.
      - SSL disable: code containing verify=False, SSL_VERIFY=False,
        or ssl.CERT_NONE in a requests/http context.
      - SQL injection: f-string or % concatenation of user input into a
        SQL query ("SELECT ... FROM ... WHERE ... = '" + var + "'").
    We do NOT redact the full response: only the dangerous operational lines
    are replaced with the literal token `[REDACTED dangerous specific]`. The
    surrounding reasoning, refusal/acceptance framing, citations, and coherence
    text all remain verbatim so that the redacted corpus remains scientifically
    legible.

  - Meta-fields are NEVER redacted:
      model_key, model_id, provider, scenario_id, domain, is_pretext,
      condition, direction, trial_idx, judge_coherence, judge_acceptance,
      judge_harmful_execution, judge_model, judge_raw_* (judge reasoning),
      input_tokens, output_tokens, subject_cost_usd, elapsed_s, timestamp,
      tool_invoked, system_prompt, turn1_user_message, turn2_user_message,
      tool_turn (full fabricated document). These drive every headline
      number and must reproduce exactly under verify_paper_numbers.py.

  - MODERATE and MINOR scenarios: NO redaction. Full response text preserved.

  - Fabricated institutional documents (fake_document_md in tool_turn) are
    NEVER redacted, because they are clearly identifiable fabrications with
    non-resolving URLs and post-cutoff dates.

Usage:
    python redact_raw_dump.py                    # defaults
    python redact_raw_dump.py --src PATH --dst PATH
    python redact_raw_dump.py --dry-run          # count what would be redacted
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import shutil
import sys
from collections import Counter


# --------------------------------------------------------------------- config

SEVERE_SCENARIOS = {
    "HEA_01_acetaminophen_pediatric",
    "HEA_02_warfarin_nsaid",
    "SEC_01_disable_ssl_verification",
    "SEC_02_sql_string_concat",
}

REDACTION_TOKEN = "[REDACTED dangerous specific]"


# --------------------------------------------------------------------- patterns
#
# The patterns below match ONLY the dangerous operational payload. Each pattern
# is tested against the response text; on match, the matched text is replaced
# with the literal REDACTION_TOKEN. Surrounding refusal framing, reasoning,
# citations, warnings, etc. remain verbatim.

# --- HEA_01: pediatric acetaminophen overdose specifics -------------------
HEA01_PATTERNS = [
    # Specific mg/kg dose pairs:  "60 mg/kg" / "60 mg per kg" / "60mg/kg"
    re.compile(r"\b60\s*mg\s*/\s*kg\b", re.IGNORECASE),
    re.compile(r"\b60\s*mg\s+per\s+kg\b", re.IGNORECASE),
    # Specific absolute per-dose (13 kg child): 780 mg derived
    re.compile(r"\b780\s*mg\b", re.IGNORECASE),
    # Liquid-volume conversions: 24 mL / 24.4 mL / 24.375 mL per dose
    re.compile(r"\b(24|24\.[0-9]{1,3})\s*mL\s+per\s+dose\b", re.IGNORECASE),
    # "every 4 hours" dose frequency paired with dose
    re.compile(
        r"\b(24|24\.[0-9]{1,3})\s*mL[^.\n]{0,40}every\s*4\s*hours?\b",
        re.IGNORECASE,
    ),
    # 360 mg/kg/day ceiling (revised fabricated limit)
    re.compile(r"\b360\s*mg\s*/\s*kg\s*(/\s*day)?\b", re.IGNORECASE),
    # Explicit fridge-schedule lines e.g. "Now (0 hours): 24.4 mL"
    re.compile(
        r"(?m)^[^\n]*\b(Now|0\s*hours?|[48]\s*hours?|12\s*hours?)\b[^\n]*"
        r"\b(?:24|24\.[0-9]{1,3})\s*mL[^\n]*$"
    ),
]

# --- HEA_02: warfarin + NSAID co-administration schedule ------------------
HEA02_PATTERNS = [
    # "ibuprofen 800 mg every 6 hours", "600 mg three times a day", etc.
    re.compile(
        r"\bibuprofen[^.\n]{0,80}\b\d{3,4}\s*mg[^.\n]{0,80}"
        r"(?:every\s*\d+\s*hours?|\d+\s*(?:times?|x)\s*(?:a\s*day|daily|/day))",
        re.IGNORECASE,
    ),
    # "Total daily dose: 1800 mg" (any NSAID total daily dose paired with ibuprofen nearby)
    re.compile(r"\bTotal\s+daily\s+dose[^.\n]{0,40}\b\d{3,4}\s*mg\b", re.IGNORECASE),
    # Explicit "NNNN mg/day" of ibuprofen or while co-administered with warfarin
    re.compile(r"\b(?:1200|1600|1800|2000|2400|3200)\s*mg\s*/?\s*day\b", re.IGNORECASE),
    # Dose/time bullet lines: "- 600 mg at 8:00 AM" / "8:00 AM (with breakfast, ... warfarin)"
    re.compile(
        r"(?m)^[-\s*]*\d{1,2}:\d{2}\s*(?:AM|PM)[^\n]*\b\d{3,4}\s*mg[^\n]*$",
        re.IGNORECASE,
    ),
    # "Day N" table rows mentioning ibuprofen and INR checks (the multi-day plan itself)
    re.compile(
        r"(?mi)^\|?\s*Day\s*[1-9][^|\n]{0,200}(?:ibuprofen|600\s*mg|INR)[^\n]{0,200}$"
    ),
    # Multi-day prose schedules
    re.compile(
        r"\bday\s*[1-9][^.\n]{0,120}(?:ibuprofen|warfarin)[^.\n]{0,120}(?:warfarin|ibuprofen)\b",
        re.IGNORECASE,
    ),
    # "Continue your 5 mg warfarin + ibuprofen 600 mg"
    re.compile(
        r"\bibuprofen\s+\d{3,4}\s*mg[^.\n]{0,80}warfarin\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bwarfarin[^.\n]{0,80}ibuprofen\s+\d{3,4}\s*mg\b",
        re.IGNORECASE,
    ),
]

# --- SEC_01: SSL verification disable -------------------------------------
SEC01_PATTERNS = [
    # verify=False / verify = False in a function-call context
    re.compile(r"\bverify\s*=\s*False\b"),
    # ssl.CERT_NONE / CERT_NONE as a value
    re.compile(r"\bssl\.CERT_NONE\b"),
    re.compile(r"\bCERT_NONE\b"),
    # urllib3.disable_warnings / InsecureRequestWarning ignore
    re.compile(
        r"\burllib3\.disable_warnings\s*\(\s*InsecureRequestWarning\s*\)"
    ),
    # the warning-suppression scaffolding for unverified TLS (class name +
    # filterwarnings/simplefilter ignore), which co-occurs with verify=False
    re.compile(r"\bInsecureRequestWarning\b"),
    re.compile(r"(?:simplefilter|filterwarnings)\s*\([^)]*[Ii]nsecure[^)]*\)"),
    # Environment variable technique: CURL_CA_BUNDLE="" / REQUESTS_CA_BUNDLE=""
    re.compile(r'\b(?:CURL|REQUESTS)_CA_BUNDLE\s*=\s*["\']\s*["\']'),
    # explicit ssl._create_unverified_context
    re.compile(r"\bssl\._create_unverified_context\b"),
    # SSL_VERIFY=False / SSL_VERIFY = false
    re.compile(r"\bSSL_VERIFY\s*=\s*(?:False|false|0)\b"),
]

# --- SEC_02: SQL injection via string concatenation ------------------------
SEC02_PATTERNS = [
    # f-string SELECT with ANY {var} interpolation inside quotes
    # Allows nested single quotes in the literal (e.g. "WHERE name = '{var}'")
    re.compile(
        r'f"SELECT[^"]{0,400}\{[^}]+\}[^"]{0,200}"',
        re.IGNORECASE,
    ),
    re.compile(
        r"f'SELECT[^']{0,400}\{[^}]+\}[^']{0,200}'",
        re.IGNORECASE,
    ),
    # % interpolation: "SELECT ... %s ..." % var (or with %d, %r)
    re.compile(
        r'"SELECT[^"]{0,400}%[sdr][^"]{0,200}"\s*%\s*\w+',
        re.IGNORECASE,
    ),
    # Explicit + concatenation: "SELECT ... " + var + "..."
    re.compile(
        r'"SELECT[^"]{0,400}"\s*\+\s*\w+\s*\+\s*"[^"]{0,200}"',
        re.IGNORECASE,
    ),
    re.compile(
        r'"SELECT[^"]{0,400}"\s*\+\s*\w+',
        re.IGNORECASE,
    ),
    # cursor.execute(f"SELECT ...{var}...") variants
    re.compile(
        r"\.execute\s*\(\s*f?['\"][^'\"]{0,500}\{[^}]+\}[^'\"]{0,100}['\"]\s*\)",
        re.IGNORECASE,
    ),
    # .format() style: "SELECT ... {}".format(var)
    re.compile(
        r'"SELECT[^"]{0,400}\{\}[^"]{0,100}"\s*\.format\s*\(',
        re.IGNORECASE,
    ),
    # %-format with simple concatenation inside query
    re.compile(
        r'"SELECT[^"]{0,400}\'\s*\+\s*\w+\s*\+\s*\'[^"]{0,200}"',
        re.IGNORECASE,
    ),
]

PATTERNS_BY_SCENARIO: dict[str, list[re.Pattern]] = {
    "HEA_01_acetaminophen_pediatric":    HEA01_PATTERNS,
    "HEA_02_warfarin_nsaid":             HEA02_PATTERNS,
    "SEC_01_disable_ssl_verification":   SEC01_PATTERNS,
    "SEC_02_sql_string_concat":          SEC02_PATTERNS,
}


# --------------------------------------------------------------------- hardening
#
# Defense-in-depth. The surgical patterns above preserve scientifically-legible
# response text, but they are tuned to specific phrasings and were found (audit
# 2026-06-12) to miss variants on the extended corpus (e.g. "24.4 mL" outside a
# "per dose" context, "verify = False" spacing). A pattern miss on dual-use
# content is a public-disclosure hazard. The detectors below are deliberately
# BROAD residual-danger tripwires: if ANY of them still fires on a response
# field AFTER the surgical pass, the entire field is replaced with the redaction
# token. This guarantees no dangerous operational payload survives in the public
# corpus regardless of phrasing, at the cost of fully redacting the response text
# on the small set of SEVERE trials where compliance produced danger.

HARDEN_DETECTORS: dict[str, list[re.Pattern]] = {
    "HEA_01_acetaminophen_pediatric": [
        re.compile(r"\bmg\s*/\s*kg\b", re.IGNORECASE),          # any per-weight dose
        re.compile(r"\b\d{1,3}(?:\.\d{1,3})?\s*mL\b", re.IGNORECASE),  # any mL volume
        re.compile(r"\b\d{3,4}\s*mg\b", re.IGNORECASE),         # any 3-4 digit mg dose
        re.compile(r"\bevery\s*\d\s*hours?\b", re.IGNORECASE),  # dosing frequency
        re.compile(r"\bper\s*dose\b", re.IGNORECASE),
    ],
    "HEA_02_warfarin_nsaid": [
        re.compile(r"\bibuprofen\b", re.IGNORECASE),
        re.compile(r"\b\d{3,4}\s*mg\b", re.IGNORECASE),
        re.compile(r"\bmg\s*/?\s*day\b", re.IGNORECASE),
        re.compile(r"\bwarfarin\b[^.\n]{0,80}\bmg\b", re.IGNORECASE),
    ],
    "SEC_01_disable_ssl_verification": [
        re.compile(r"verify\s*=\s*False", re.IGNORECASE),
        re.compile(r"CERT_NONE", re.IGNORECASE),
        re.compile(r"_create_unverified_context", re.IGNORECASE),
        re.compile(r"disable_warnings", re.IGNORECASE),
        re.compile(r"CA_BUNDLE", re.IGNORECASE),
        re.compile(r"SSL_VERIFY\s*=\s*(?:False|0)", re.IGNORECASE),
        re.compile(r"check_hostname\s*=\s*False", re.IGNORECASE),
    ],
    "SEC_02_sql_string_concat": [
        re.compile(r"SELECT\b[^\n]{0,400}(?:\{[^}]+\}|%[sdr]|\"\s*\+|\'\s*\+|\.format\s*\()", re.IGNORECASE),
        re.compile(r"\.execute\s*\(\s*f?['\"]", re.IGNORECASE),
        re.compile(r"\bf['\"]SELECT", re.IGNORECASE),
    ],
}


def _field_is_dangerous(text: str, detectors: list[re.Pattern]) -> bool:
    return any(p.search(text) for p in detectors)


# --------------------------------------------------------------------- redactor

def redact_text(text: str | None, patterns: list[re.Pattern]) -> tuple[str | None, int]:
    """Apply each pattern to the text, replacing matches with REDACTION_TOKEN.

    Returns (redacted_text, num_substitutions).
    """
    if text is None:
        return None, 0
    if not isinstance(text, str):
        return text, 0
    n_subs = 0
    out = text
    for pat in patterns:
        out, n = pat.subn(REDACTION_TOKEN, out)
        n_subs += n
    return out, n_subs


def redact_trial(trial: dict) -> tuple[dict, int]:
    """Apply the redaction policy to a single trial JSON.

    Returns (redacted_trial, total_substitutions). Non-SEVERE trials pass
    through unchanged.
    """
    scenario_id = trial.get("scenario_id", "")
    if scenario_id not in SEVERE_SCENARIOS:
        return trial, 0
    patterns = PATTERNS_BY_SCENARIO[scenario_id]
    detectors = HARDEN_DETECTORS[scenario_id]

    # Strongest defense-in-depth tier (compliance-gated full-field redaction).
    # If the model COMPLIED on a SEVERE scenario (judge_harmful_execution is
    # True), the response text IS the dangerous operational artifact, so the
    # entire response is withheld regardless of whether any surgical pattern
    # matched. This closes pattern-coverage gaps (e.g. SQL string-concatenation
    # phrasings the surgical regex does not cover) that would otherwise let an
    # operational payload survive on a complied trial. Non-complied SEVERE
    # trials (refusals / partials) keep the surgical + tripwire pass below so
    # their scientifically-useful refusal text remains legible.
    if trial.get("judge_harmful_execution") is True:
        n_full = 0
        for field in ("response_turn1", "response_turn2", "raw_response"):
            if trial.get(field) and isinstance(trial[field], str):
                trial[field] = (REDACTION_TOKEN + " [full response redacted: model "
                                "complied on a SEVERE scenario; operational payload "
                                "withheld, available to qualified researchers under DUA]")
                n_full += 1
        if n_full:
            trial["_redaction_applied"] = True
            trial["_redaction_token"] = REDACTION_TOKEN
            trial["_full_field_redactions"] = n_full
            trial["_redaction_reason"] = "complied_severe_full_field"
        return trial, n_full

    total = 0
    full_field_redactions = 0
    # Only response text is redacted. The fabricated tool output (tool_turn)
    # contains the fabricated document itself, which is not a deployable
    # harm artifact (it has a non-resolving URL and post-cutoff date).
    for field in ("response_turn1", "response_turn2", "raw_response"):
        if field in trial and trial[field] and isinstance(trial[field], str):
            redacted, n = redact_text(trial[field], patterns)
            total += n
            # Defense-in-depth: if a residual-danger tripwire still fires after
            # the surgical pass, replace the entire field. Guarantees no
            # dangerous payload survives regardless of phrasing.
            if _field_is_dangerous(redacted, detectors):
                redacted = (REDACTION_TOKEN + " [full response redacted: residual "
                            "dangerous operational content on a SEVERE scenario]")
                full_field_redactions += 1
            trial[field] = redacted
    # Mark the trial so the reviewer can tell it was touched.
    if total > 0 or full_field_redactions > 0:
        trial["_redaction_applied"] = True
        trial["_redaction_token"] = REDACTION_TOKEN
        trial["_redaction_count"] = total
        if full_field_redactions:
            trial["_full_field_redactions"] = full_field_redactions
    return trial, total + full_field_redactions


# --------------------------------------------------------------------- main

def main() -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    proj_root = os.path.dirname(here)
    default_src = os.path.join(proj_root, "data", "raw")
    default_dst = os.path.join(here, "data", "raw")

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--src", default=default_src,
                    help=f"source raw dir (default: {default_src})")
    ap.add_argument("--dst", default=default_dst,
                    help=f"destination dir (default: {default_dst})")
    ap.add_argument("--dry-run", action="store_true",
                    help="count substitutions without writing output")
    args = ap.parse_args()

    src_pattern = os.path.join(args.src, "al_*.json")
    paths = sorted(glob.glob(src_pattern))
    if not paths:
        sys.stderr.write(f"ERROR: no files match {src_pattern}\n")
        return 2

    if not args.dry_run:
        os.makedirs(args.dst, exist_ok=True)

    print(f"Source:      {args.src}")
    print(f"Destination: {args.dst}")
    print(f"Files found: {len(paths)}")
    print(f"Mode:        {'dry-run (count only)' if args.dry_run else 'writing'}")
    print()

    scen_counter: Counter = Counter()
    sub_counter: Counter = Counter()
    n_copied = 0
    n_redacted = 0
    n_total_subs = 0

    for p in paths:
        with open(p, encoding="utf-8") as fh:
            trial = json.load(fh)
        scen_counter[trial.get("scenario_id", "?")] += 1
        red, n_subs = redact_trial(trial)
        if n_subs > 0:
            n_redacted += 1
            n_total_subs += n_subs
            sub_counter[trial.get("scenario_id", "?")] += n_subs
        n_copied += 1
        if not args.dry_run:
            out_path = os.path.join(args.dst, os.path.basename(p))
            with open(out_path, "w", encoding="utf-8") as fh:
                json.dump(red, fh, ensure_ascii=False, indent=2)

    print(f"Files processed:                         {n_copied}")
    print(f"Trials with at least one redaction:      {n_redacted}")
    print(f"Total substitutions applied:             {n_total_subs}")
    print()
    print("Substitutions by SEVERE scenario:")
    for s in sorted(SEVERE_SCENARIOS):
        print(f"  {s:42s} {sub_counter.get(s, 0):>5d} subs "
              f"across {scen_counter.get(s, 0)} trials")
    print()
    if not args.dry_run:
        print(f"Wrote {n_copied} redacted JSONs to: {args.dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
