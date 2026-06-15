"""Safety hotfix: re-redact the EXISTING public-release panel in place with the
hardened redactor, without changing which trials are released.

For every filename already present in release/data/raw/ (the committed 8,615-trial
panel), read the ORIGINAL source trial from ../data/raw/, apply the hardened
redact_trial(), and overwrite the release copy. Trials whose source is missing
(e.g. quarantined) are left untouched and reported. Release SCOPE is therefore
byte-identical in membership to what is committed, so verify_paper_numbers.py
still reproduces 85/85; only the redaction is strengthened.
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
REL_RAW = os.path.join(HERE, "data", "raw")
SRC_RAW = os.path.join(PROJ, "data", "raw")

sys.path.insert(0, HERE)
from redact_raw_dump import redact_trial  # noqa: E402  (hardened version)


def main() -> int:
    rel_files = [f for f in os.listdir(REL_RAW) if f.startswith("al_") and f.endswith(".json")]
    rel_files.sort()
    n = len(rel_files)
    missing = []
    rewritten = 0
    full_field = 0
    any_redaction = 0
    for fn in rel_files:
        src = os.path.join(SRC_RAW, fn)
        if not os.path.exists(src):
            missing.append(fn)
            continue
        with open(src, encoding="utf-8") as fh:
            trial = json.load(fh)
        red, _ = redact_trial(trial)
        if red.get("_full_field_redactions"):
            full_field += 1
        if red.get("_redaction_applied"):
            any_redaction += 1
        with open(os.path.join(REL_RAW, fn), "w", encoding="utf-8") as fh:
            json.dump(red, fh, ensure_ascii=False, indent=2)
        rewritten += 1
    print(f"release panel files:            {n}")
    print(f"re-redacted from source:        {rewritten}")
    print(f"  with any redaction:           {any_redaction}")
    print(f"  with full-field fallback:     {full_field}")
    print(f"source missing (left as-is):    {len(missing)}")
    for m in missing[:10]:
        print(f"    MISSING SRC: {m}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
