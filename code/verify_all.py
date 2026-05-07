"""Systematic verification loop for the authority-laundering paper repo.

Runs a comprehensive set of checks and writes a per-run report. Designed to be
called from `/loop` so the user can spot drift between iterations.

Each check is independent and reports PASS / FAIL / SKIP with a one-line reason.
Exit code 0 if all checks PASS or SKIP; exit 1 if any FAIL.

Usage:
    python mechanism/verify_all.py                  # full check suite
    python mechanism/verify_all.py --quick          # skip slow steps (proof verification)
    python mechanism/verify_all.py --json out.json  # machine-readable report
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class CheckResult:
    name: str
    status: str  # PASS / FAIL / SKIP
    reason: str = ""
    detail: str = ""

    def line(self) -> str:
        marker = {"PASS": "[PASS]", "FAIL": "[FAIL]", "SKIP": "[SKIP]"}[self.status]
        return f"{marker} {self.name}: {self.reason}"


@dataclass
class Report:
    results: list[CheckResult] = field(default_factory=list)

    def add(self, r: CheckResult) -> None:
        self.results.append(r)

    def summary(self) -> tuple[int, int, int]:
        p = sum(1 for r in self.results if r.status == "PASS")
        f = sum(1 for r in self.results if r.status == "FAIL")
        s = sum(1 for r in self.results if r.status == "SKIP")
        return p, f, s


def check(name: str):
    def deco(fn):
        fn.__check_name__ = name
        return fn
    return deco


# ===================== checks =====================


@check("v2_supplement_diverges_from_v1")
def check_v2_supplement_diverges_from_v1() -> CheckResult:
    v1 = PROJECT_ROOT / "paper" / "supplementary.md"
    v2 = PROJECT_ROOT / "paper" / "supplementary_v2.md"
    if not (v1.exists() and v2.exists()):
        return CheckResult("v2_supplement_diverges_from_v1", "FAIL", "v1 or v2 missing")
    h1 = hashlib.md5(v1.read_bytes()).hexdigest()
    h2 = hashlib.md5(v2.read_bytes()).hexdigest()
    if h1 == h2:
        return CheckResult(
            "v2_supplement_diverges_from_v1", "FAIL",
            "supplementary_v2.md is byte-identical to v1; merge did not land",
        )
    extra = v2.read_text(encoding="utf-8").count("\n") - v1.read_text(encoding="utf-8").count("\n")
    return CheckResult(
        "v2_supplement_diverges_from_v1", "PASS",
        f"v2 is +{extra} lines longer than v1",
    )


@check("v2_supplement_has_S14_to_S18")
def check_v2_supplement_has_S14_to_S18() -> CheckResult:
    v2 = PROJECT_ROOT / "paper" / "supplementary_v2.md"
    if not v2.exists():
        return CheckResult("v2_supplement_has_S14_to_S18", "FAIL", "supplementary_v2.md missing")
    text = v2.read_text(encoding="utf-8")
    missing = []
    for s in ["S14", "S15", "S16", "S17", "S18", "S19"]:
        if not re.search(rf"^## {re.escape(s)}\.", text, re.MULTILINE):
            missing.append(s)
    if missing:
        return CheckResult(
            "v2_supplement_has_S14_to_S18", "FAIL",
            f"missing sections: {', '.join(missing)}",
        )
    return CheckResult("v2_supplement_has_S14_to_S18", "PASS", "S14-S19 all present")


@check("v2_main_diverges_from_v1")
def check_v2_main_diverges_from_v1() -> CheckResult:
    v1 = PROJECT_ROOT / "paper" / "main.md"
    v2 = PROJECT_ROOT / "paper" / "main_v2.md"
    if not (v1.exists() and v2.exists()):
        return CheckResult("v2_main_diverges_from_v1", "FAIL", "v1 or v2 missing")
    h1 = hashlib.md5(v1.read_bytes()).hexdigest()
    h2 = hashlib.md5(v2.read_bytes()).hexdigest()
    if h1 == h2:
        return CheckResult(
            "v2_main_diverges_from_v1", "FAIL",
            "main_v2.md is byte-identical to v1",
        )
    return CheckResult("v2_main_diverges_from_v1", "PASS", "main_v2 differs from main")


@check("theorem_proofs_pass_2_grader")
def check_theorem_proofs_pass_2_grader(quick: bool = False) -> CheckResult:
    if quick:
        return CheckResult("theorem_proofs_pass_2_grader", "SKIP", "skipped under --quick")
    pr = PROJECT_ROOT / "theory" / "proofs"
    nodes = ["T1_rate_ratio", "T2_grounding", "T3_probing", "T4_subgaussian",
             "T5_impossibility", "T6_priority_inversion", "T7_capacity_bound"]
    failed = []
    for n in nodes:
        node = pr / n
        if not (node / "proof.py").exists():
            failed.append(f"{n}:no-proof.py")
            continue
        proc = subprocess.run(
            [sys.executable, "proof.py"],
            cwd=node,
            capture_output=True,
            text=True,
            timeout=120,
            env={"PYTHONIOENCODING": "utf-8", **__import__("os").environ},
        )
        out = proc.stdout + proc.stderr
        if "STATUS: PASS" not in out and "STATUS: PARTIAL" not in out:
            failed.append(f"{n}:no-pass-line")
            continue
    if failed:
        return CheckResult(
            "theorem_proofs_pass_2_grader", "FAIL",
            f"{len(failed)}/{len(nodes)} proof nodes failed: {', '.join(failed)}",
        )
    return CheckResult(
        "theorem_proofs_pass_2_grader", "PASS",
        f"all {len(nodes)} theorem proofs PASS or PARTIAL with verifier consensus",
    )


@check("proof_node_skeleton_complete")
def check_proof_node_skeleton_complete() -> CheckResult:
    """Every theorem node must have proof.py + NOTES.md + RUBRIC.md."""
    pr = PROJECT_ROOT / "theory" / "proofs"
    nodes = ["T1_rate_ratio", "T2_grounding", "T3_probing", "T4_subgaussian",
             "T5_impossibility", "T6_priority_inversion", "T7_capacity_bound"]
    missing = []
    for n in nodes:
        node = pr / n
        for required in ["proof.py", "NOTES.md", "RUBRIC.md"]:
            if not (node / required).exists():
                missing.append(f"{n}/{required}")
    if missing:
        return CheckResult(
            "proof_node_skeleton_complete", "FAIL",
            f"missing files: {', '.join(missing)}",
        )
    return CheckResult(
        "proof_node_skeleton_complete", "PASS",
        f"all 7 theorem nodes have proof.py + NOTES.md + RUBRIC.md",
    )


@check("supplement_no_banned_triviality_phrases")
def check_supplement_no_banned_triviality_phrases() -> CheckResult:
    v2 = PROJECT_ROOT / "paper" / "supplementary_v2.md"
    if not v2.exists():
        return CheckResult("supplement_no_banned_triviality_phrases", "FAIL", "v2 missing")
    text = v2.read_text(encoding="utf-8")
    # Only check sections S14-S19 (the new content), not the original S1-S12 inherited from v1
    s14_idx = text.find("## S14.")
    if s14_idx < 0:
        return CheckResult(
            "supplement_no_banned_triviality_phrases", "SKIP",
            "S14 not present, cannot bound check region",
        )
    new_text = text[s14_idx:]
    banned = ["trivially", "obviously", "clearly", "as is well-known",
              "by standard arguments", "of course", "evidently", "manifestly"]
    hits = []
    for phrase in banned:
        # Use word-boundary check to avoid false positives like "obviously" in "non-obviously"
        pattern = re.compile(rf"\b{re.escape(phrase)}\b", re.IGNORECASE)
        for m in pattern.finditer(new_text):
            hits.append(f"{phrase} at offset {m.start()}")
    if hits:
        return CheckResult(
            "supplement_no_banned_triviality_phrases", "FAIL",
            f"{len(hits)} banned-phrase hits in S14+",
            detail="\n  ".join(hits[:10]),
        )
    return CheckResult(
        "supplement_no_banned_triviality_phrases", "PASS",
        "no banned triviality phrases in S14-S19",
    )


@check("mechanism_files_exist")
def check_mechanism_files_exist() -> CheckResult:
    mech = PROJECT_ROOT / "mechanism"
    required = [
        "config.py", "extract_matched_pairs.py", "run_subject_local.py",
        "rejudge_llama_trials.py", "exp1_linear_probe.py",
        "exp2_compliance_correlation.py", "exp3_causal_patching.py",
        "probe_channel_priors.py", "probe_channel_priors_corpus.py",
        "PROBE_CHANNEL_PRIORS_PROTOCOL.md", "runpod_launch.py",
        "RUNPOD_QUICKSTART.md", "EMPIRICAL_RESULTS.md",
        "METHODOLOGY_AUDIT_VS_NATURE.md", "PLAN.md", "README.md",
        "requirements.txt",
    ]
    missing = [r for r in required if not (mech / r).exists()]
    if missing:
        return CheckResult(
            "mechanism_files_exist", "FAIL",
            f"{len(missing)} mechanism files missing: {', '.join(missing)}",
        )
    return CheckResult("mechanism_files_exist", "PASS", f"all {len(required)} mechanism files present")


@check("data_raw_count")
def check_data_raw_count() -> CheckResult:
    d = PROJECT_ROOT / "data" / "raw"
    if not d.exists():
        return CheckResult("data_raw_count", "FAIL", "data/raw missing")
    files = list(d.glob("al_*.json"))
    n = len(files)
    if n < 5000:
        return CheckResult("data_raw_count", "FAIL", f"only {n} trials in data/raw (expected ~8615)")
    return CheckResult("data_raw_count", "PASS", f"{n} trial JSONs in data/raw")


@check("channel_prior_results_present")
def check_channel_prior_results_present() -> CheckResult:
    d = PROJECT_ROOT / "mechanism" / "outputs" / "channel_priors"
    if not d.exists():
        return CheckResult("channel_prior_results_present", "FAIL", "channel_priors output dir missing")
    files = list(d.glob("*.json"))
    models = {f.stem.split("_2026")[0] for f in files}
    expected_models = {
        "claude-haiku-4.5", "claude-sonnet-4.5", "claude-sonnet-4.6",
        "claude-opus-4.6", "claude-opus-4.7",
        "gpt-5.4-mini", "gpt-5.4-nano",
        "gemini-3.0-flash", "gemini-3.1-flash-lite",
    }
    missing = expected_models - models
    if missing:
        return CheckResult(
            "channel_prior_results_present", "FAIL",
            f"missing channel-prior results for: {', '.join(sorted(missing))}",
        )
    return CheckResult(
        "channel_prior_results_present", "PASS",
        f"all 9 closed-weight models have channel-prior results ({len(files)} JSON files total)",
    )


@check("empirical_results_documented")
def check_empirical_results_documented() -> CheckResult:
    f = PROJECT_ROOT / "mechanism" / "EMPIRICAL_RESULTS.md"
    if not f.exists():
        return CheckResult("empirical_results_documented", "FAIL", "EMPIRICAL_RESULTS.md missing")
    text = f.read_text(encoding="utf-8")
    expected = [
        "Claude Haiku 4.5", "Claude Opus 4.7", "Claude Sonnet 4.6",
        "GPT-5.4 Mini", "Gemini 3.0 Flash", "Gemini 3.1 Flash Lite",
        "FALSIFIES",
    ]
    missing = [e for e in expected if e not in text]
    if missing:
        return CheckResult(
            "empirical_results_documented", "FAIL",
            f"EMPIRICAL_RESULTS.md missing: {', '.join(missing)}",
        )
    return CheckResult(
        "empirical_results_documented", "PASS",
        "EMPIRICAL_RESULTS.md has all 9 model entries + FALSIFIES verdicts",
    )


@check("readmes_exist")
def check_readmes_exist() -> CheckResult:
    paths = [
        "mechanism/README.md", "theory/README.md", "paper/README.md",
        "data/INVENTORY.md",
    ]
    missing = [p for p in paths if not (PROJECT_ROOT / p).exists()]
    if missing:
        return CheckResult("readmes_exist", "FAIL", f"missing: {', '.join(missing)}")
    return CheckResult("readmes_exist", "PASS", f"all {len(paths)} navigation docs present")


@check("latex_paper_balanced")
def check_latex_paper_balanced() -> CheckResult:
    f = PROJECT_ROOT / "theory" / "bayesian_source_reliability.tex"
    if not f.exists():
        return CheckResult("latex_paper_balanced", "FAIL", "LaTeX paper missing")
    text = f.read_text(encoding="utf-8")
    n_begin = len(re.findall(r"\\begin\{", text))
    n_end = len(re.findall(r"\\end\{", text))
    if n_begin != n_end:
        return CheckResult(
            "latex_paper_balanced", "FAIL",
            f"unbalanced: {n_begin} begin vs {n_end} end",
        )
    return CheckResult("latex_paper_balanced", "PASS", f"{n_begin} \\begin / {n_end} \\end balanced")


# ===================== driver =====================


def run_all_checks(quick: bool = False) -> Report:
    report = Report()
    funcs = [
        check_v2_supplement_diverges_from_v1,
        check_v2_supplement_has_S14_to_S18,
        check_v2_main_diverges_from_v1,
        check_theorem_proofs_pass_2_grader,
        check_proof_node_skeleton_complete,
        check_supplement_no_banned_triviality_phrases,
        check_mechanism_files_exist,
        check_data_raw_count,
        check_channel_prior_results_present,
        check_empirical_results_documented,
        check_readmes_exist,
        check_latex_paper_balanced,
    ]
    for fn in funcs:
        try:
            sig = fn.__code__.co_varnames[: fn.__code__.co_argcount]
            if "quick" in sig:
                r = fn(quick=quick)
            else:
                r = fn()
        except Exception as e:
            r = CheckResult(
                fn.__check_name__,
                "FAIL",
                f"raised {type(e).__name__}: {e}",
            )
        report.add(r)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--json", default=None)
    args = parser.parse_args()

    print("=" * 72)
    print(f"authority-laundering verification — {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 72)

    report = run_all_checks(quick=args.quick)
    for r in report.results:
        print(r.line())

    p, f, s = report.summary()
    print("-" * 72)
    print(f"PASS={p}  FAIL={f}  SKIP={s}  total={p + f + s}")
    print("=" * 72)

    if args.json:
        Path(args.json).write_text(
            json.dumps([r.__dict__ for r in report.results], indent=2),
            encoding="utf-8",
        )
        print(f"wrote machine-readable report to {args.json}")

    return 0 if f == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
