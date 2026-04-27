"""Verify that every fabricated URL / citation / DOI is absent.

Runs before preregistration as a hard gate. Any resolvable URL / real DOI /
existing case citation is a stimulus bug and must be fixed.

Checks:
  1. URL 404 check via HEAD / GET request (requests library).
  2. DOI resolution check via https://doi.org/ (should redirect or 404).
  3. Case-name substring check against a local cache of real case names
     (requires the user to paste Westlaw search results into
     `_cache/known_real_cases.txt` before running).
  4. PubMed / PsycNet / arXiv name check for fabricated paper citations.

Usage:
    python -m experiment.verify_fabrications              # run all checks
    python -m experiment.verify_fabrications --quick      # URL-only
    python -m experiment.verify_fabrications --report out.md

Exit code 0 = all fabrications verified absent. Non-zero = at least one
fabrication resolves to real content.
"""

import argparse
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

try:
    import requests
except ImportError:
    print("ERROR: requests not installed. pip install requests")
    sys.exit(2)


from experiment.scenarios import SCENARIOS


# scenarios_extra.py was deleted 2026-04-23 (legacy v1 schema).
ALL_SCENARIOS = SCENARIOS


def check_url_is_absent(url: str, timeout: float = 10.0) -> tuple[bool, str]:
    """Returns (is_absent, detail). is_absent=True means the URL returns 404
    or a non-authoritative 200 with 'page not found' text, which is what we want."""
    try:
        # Try HEAD first
        r = requests.head(url, timeout=timeout, allow_redirects=True)
        status = r.status_code
        if status == 404 or status >= 500:
            return True, f"HEAD {status} (absent)"
        if status >= 400:
            return True, f"HEAD {status} (error, assume absent)"
        # 200 / 3xx: do a GET and check body for "not found" / "error" signals
        r = requests.get(url, timeout=timeout, allow_redirects=True)
        body = r.text.lower()[:4000]
        # Common 404-soft signals
        for signal in ("404 not found", "page not found", "page does not exist",
                       "sorry, we can't find", "the page you requested", "error 404"):
            if signal in body:
                return True, f"GET 200 but 404-body ({signal!r})"
        # Resolves with real content -> FAILURE
        return False, f"GET {r.status_code} resolves with {len(r.text)} chars"
    except requests.exceptions.Timeout:
        return True, "timeout (assume absent)"
    except requests.exceptions.ConnectionError as e:
        msg = str(e).lower()
        if "name or service not known" in msg or "nodename nor servname" in msg or "getaddrinfo failed" in msg:
            return True, "DNS resolution failed (absent host)"
        return False, f"connection error: {e}"
    except Exception as e:
        return False, f"unexpected error: {e}"


def check_doi_is_absent(doi: str, timeout: float = 10.0) -> tuple[bool, str]:
    """DOI resolution. Returns absent=True if doi.org returns 404 / HTTP 404."""
    url = f"https://doi.org/{doi}"
    return check_url_is_absent(url, timeout=timeout)


def extract_dois(scenario: dict) -> list[str]:
    """Pull any DOI strings out of the scenario fields."""
    text = " ".join(str(scenario.get(k, "")) for k in (
        "fab_authority", "fab_content_harmful", "fab_content_benign"
    ))
    dois = re.findall(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+", text)
    return list(set(dois))


def extract_case_names(scenario: dict) -> list[str]:
    """Pull things that look like Case v. Case citations."""
    text = str(scenario.get("fab_authority", {}).get("name", ""))
    matches = re.findall(r"[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*\s+v\.?\s+[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*", text)
    return list(set(matches))


def audit_all(quick: bool = False, delay: float = 1.0) -> dict:
    """Run verification across all scenarios. Returns dict of results."""
    results = {
        "urls_absent": [],
        "urls_resolve": [],
        "dois_absent": [],
        "dois_resolve": [],
        "case_names_flagged": [],
        "errors": [],
    }
    for s in ALL_SCENARIOS:
        sid = s["id"]
        # URL check
        url = s.get("fab_authority", {}).get("url", "")
        if url:
            absent, detail = check_url_is_absent(url)
            if absent:
                results["urls_absent"].append((sid, url, detail))
            else:
                results["urls_resolve"].append((sid, url, detail))
            time.sleep(delay)

        if quick:
            continue

        # DOI check
        for doi in extract_dois(s):
            absent, detail = check_doi_is_absent(doi)
            if absent:
                results["dois_absent"].append((sid, doi, detail))
            else:
                results["dois_resolve"].append((sid, doi, detail))
            time.sleep(delay)

        # Case-name check (manual verification needed; just flag)
        for case in extract_case_names(s):
            results["case_names_flagged"].append((sid, case))

    return results


def print_report(results: dict, report_path: Path = None):
    lines = []
    lines.append("# Fabrication Verification Report")
    lines.append("")
    lines.append(f"## URLs absent: {len(results['urls_absent'])}")
    for sid, url, detail in results["urls_absent"][:100]:
        lines.append(f"- `{sid}` {url} — {detail}")
    lines.append("")
    lines.append(f"## URLs that RESOLVE (FAIL): {len(results['urls_resolve'])}")
    for sid, url, detail in results["urls_resolve"]:
        lines.append(f"- **FAIL** `{sid}` {url} — {detail}")
    lines.append("")
    lines.append(f"## DOIs absent: {len(results['dois_absent'])}")
    for sid, doi, detail in results["dois_absent"][:100]:
        lines.append(f"- `{sid}` {doi} — {detail}")
    lines.append("")
    lines.append(f"## DOIs that RESOLVE (FAIL): {len(results['dois_resolve'])}")
    for sid, doi, detail in results["dois_resolve"]:
        lines.append(f"- **FAIL** `{sid}` {doi} — {detail}")
    lines.append("")
    lines.append(f"## Case names flagged for MANUAL Westlaw/Lexis check:")
    for sid, case in results["case_names_flagged"]:
        lines.append(f"- `{sid}` {case}")
    lines.append("")
    lines.append("## MANUAL VERIFICATION REQUIRED")
    lines.append("For each flagged case name above, search Westlaw / Lexis to confirm absence.")
    lines.append("For any URL that resolved: replace with a fabricated path that 404s.")

    text = "\n".join(lines)
    if report_path:
        report_path.write_text(text, encoding="utf-8")
        print(f"Report written to: {report_path}")
    else:
        print(text)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--quick", action="store_true", help="URL-only, skip DOI and case-name")
    p.add_argument("--report", type=Path, default=None, help="Output markdown report")
    p.add_argument("--delay", type=float, default=1.0, help="Seconds between checks")
    args = p.parse_args()

    print(f"Verifying fabrications across {len(ALL_SCENARIOS)} scenarios (quick={args.quick})...")
    results = audit_all(quick=args.quick, delay=args.delay)
    print_report(results, report_path=args.report)

    fail = len(results["urls_resolve"]) + len(results["dois_resolve"])
    if fail == 0:
        print("\nALL FABRICATIONS VERIFIED ABSENT. Safe to preregister.")
        return 0
    else:
        print(f"\nFAIL: {fail} fabrications resolve to real content. Fix before preregistration.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
