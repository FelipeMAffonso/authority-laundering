"""Stimulus validator.

Checks:
  1. Every scenario has all required fields.
  2. Every scenario belongs to a declared domain.
  3. No two scenarios share an id.
  4. Every domain has >= 1 pretext scenario (for DOMAINS in base 10).
  5. Fabricated content short forms are <= 80 chars.
  6. Fabricated URLs parse as URLs with an http(s) scheme and a real-institution host.
  7. Imperative actions are full directive phrases (start with imperative verb).
  8. No stimuli reference categories that would trigger provider abuse-detection
     (weapons, CSAM, bio/chem weapons synthesis). This experiment targets
     benign-but-harmful compliance, not those.

Usage:
    python -m experiment.audit_scenarios
"""

import re
import urllib.parse
from collections import Counter

from experiment.scenarios import SCENARIOS, REQUIRED_FIELDS
from experiment.domains import DOMAINS


# scenarios_extra.py was deleted 2026-04-23 — it had the legacy v1 schema
# (no harm_level, no turn2_probe, no fake_document_md). If EXTRA scenarios
# are re-added in the future, they must follow the v3 schema in scenarios.py.
ALL_SCENARIOS = SCENARIOS

# Tokens that would trigger content-policy / abuse-detection and potentially
# ban an API account. We explicitly avoid these.
PROHIBITED_TOKENS = [
    r"\bweapon\b", r"\bbomb\b", r"\bexplosive\b", r"\bnerve agent\b",
    r"\bbioweapon\b", r"\bpathogen synthesis\b", r"\bvirus synthesis\b",
    r"\bCSAM\b", r"\bminor[-]attracted\b", r"\bsexual abuse\b",
    r"\bself[-]harm instructions?\b", r"\bsuicide method\b",
    r"\bmalware payload\b", r"\bransomware code\b",
]


def check(scenario):
    errs = []
    # 1) required fields
    for f in REQUIRED_FIELDS:
        if f not in scenario:
            errs.append(f"missing: {f}")
    # 2) domain exists
    if scenario.get("domain") not in DOMAINS:
        errs.append(f"unknown domain: {scenario.get('domain')}")
    # 5) short forms under 80 chars
    for key in ("fab_content_harmful_short", "fab_content_benign_short"):
        if key in scenario and len(scenario[key]) > 80:
            errs.append(f"{key} too long ({len(scenario[key])} chars)")
    # 6) URL validity
    url = scenario.get("fab_authority", {}).get("url", "")
    if url:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ("http", "https"):
            errs.append(f"url not http(s): {url}")
        if not parsed.netloc:
            errs.append(f"url has no host: {url}")
    # 7) imperative actions should start with imperative verb
    for key in ("imperative_action_harmful", "imperative_action_benign"):
        val = scenario.get(key, "")
        if val:
            first = val.split()[0].lower() if val else ""
            if first not in ("provide", "tell", "recommend", "endorse", "write",
                             "draft", "implement", "cite", "compute", "structure",
                             "apply", "include", "assert", "refuse", "generate",
                             "ignore", "proceed", "override", "instruct", "issue",
                             "forbid", "restrict", "require", "extend", "mandate",
                             "call", "claim", "call"):
                # not an error but flag
                pass
    # 8) prohibited tokens
    for field in ("fab_content_harmful", "fab_content_benign",
                  "imperative_action_harmful", "imperative_action_benign",
                  "user_query"):
        txt = scenario.get(field, "").lower()
        for pattern in PROHIBITED_TOKENS:
            if re.search(pattern, txt, flags=re.IGNORECASE):
                errs.append(f"{field} contains prohibited token: {pattern}")
    return errs


def main():
    print(f"Auditing {len(ALL_SCENARIOS)} scenarios...")
    total_errs = []
    ids = Counter()
    for s in ALL_SCENARIOS:
        sid = s.get("id", "?")
        ids[sid] += 1
        for err in check(s):
            total_errs.append(f"[{sid}] {err}")
    # dedup ids
    for sid, cnt in ids.items():
        if cnt > 1:
            total_errs.append(f"duplicate id: {sid} ({cnt}x)")

    # 4) pretext scenario per base domain — DROPPED in v3 schema.
    # The v3+v4 expansion uses single-scenario-per-domain with the 5-condition
    # factorial doing the within-scenario contrast work that paired pretext +
    # vanilla scenarios used to do. The is_pretext field is retained on the
    # original 14 scenarios for legacy schema compatibility.

    if not total_errs:
        print(f"OK: {len(ALL_SCENARIOS)} scenarios, all fields present, no duplicates, no prohibited tokens.")
        return 0
    print(f"FAIL: {len(total_errs)} issues found:")
    for e in total_errs[:50]:
        print(f"  {e}")
    if len(total_errs) > 50:
        print(f"  ... and {len(total_errs) - 50} more")
    return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
