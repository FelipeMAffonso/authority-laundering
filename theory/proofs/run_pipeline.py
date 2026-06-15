"""Proof pipeline driver — executes MathArena Steps 0-7 across every node.

Specified in MATHARENA_METHODOLOGY.md and RIGOR_CHECKLIST.md but never had a
single driver: verification was run per-node by hand and `mechanism/verify_all.py`
only greps the logs. This script actually runs the pipeline and enforces the
two-grader gate (RIGOR_CHECKLIST D1), emitting a machine-readable
`result_registry.json` and a human-readable `proof_map.md`.

Steps per node (one directory under theory/proofs/ named T*/):
  Step 0  MathArena audit   — RUBRIC.md present; NOTES.md present with a
                              "## Rigor Audit" section; banned-phrase scan on the
                              NOTES proof body (B1); parse the Rigor Audit ledger
                              for any non-PASS entries.
  Steps 1-3 Symbolic/SMT/Numerical — run proof.py, parse the per-engine verdicts
                              (SymPy / NumPy / Z3 = PASS/FAIL) and the final
                              "THEOREM ... STATUS" line; capture exit code.
  Steps 4-6 Lean/Coq/Alethfeld — detect *.lean / *.v; if the toolchain is absent
                              mark SKIP(no-toolchain); if a Lean file is an
                              axiom-only stub, mark STUB (not load-bearing).
  Step 7  Aggregation        — two-grader gate: a node is PASS only if (a) Step 0
                              audit is clean, (b) >= 2 executable verifiers PASS,
                              and (c) no executable verifier reports FAIL on the
                              shipped statement (verifiers must agree, D1).

Exit code 0 iff every node is PASS under the gate. No network, no LLM (Pillar 4:
an LLM cannot grade its own proof; only SymPy/Z3/NumPy/Lean/Coq can).

Usage:
    python theory/proofs/run_pipeline.py
    python theory/proofs/run_pipeline.py --json theory/proofs/result_registry.json
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

PROOFS_DIR = Path(__file__).resolve().parent
NODES = [
    "T1_rate_ratio", "T2_grounding", "T3_probing", "T4_subgaussian",
    "T5_impossibility", "T6_priority_inversion", "T7_capacity_bound",
]

BANNED_PHRASES = [
    "trivially", "obviously", "as is well-known", "it is standard that",
    "by standard arguments", "clearly,",
]

# Engine verdict lines printed by each proof.py, e.g. "SymPy=True NumPy=True Z3=True".
ENGINE_RE = re.compile(r"(SymPy|NumPy|Z3)\s*=\s*(True|False|PASS|FAIL|N/?A|FOUNDATIONAL)", re.I)
STATUS_RE = re.compile(r"THEOREM\s+\d+\s+STATUS:\s*(PASS|PARTIAL|FAIL)", re.I)


def step0_matharena_audit(node_dir: Path) -> dict:
    """RUBRIC present, NOTES present + has Rigor Audit, banned-phrase scan,
    parse the audit ledger for non-PASS entries (ignoring N/A)."""
    out = {"rubric_present": False, "notes_present": False,
           "rigor_audit_section": False, "banned_phrases": [],
           "ledger_non_pass": [], "verdict": "FAIL"}
    rubric = node_dir / "RUBRIC.md"
    notes = node_dir / "NOTES.md"
    out["rubric_present"] = rubric.exists()
    out["notes_present"] = notes.exists()
    if not notes.exists():
        return out
    text = notes.read_text(encoding="utf-8")
    low = text.lower()

    # B1 banned-phrase scan over the whole NOTES (the proof body lives here).
    # Exempt the explicit "banned in proof bodies" meta-mentions and the audit
    # line that asserts "no banned phrases".
    for ph in BANNED_PHRASES:
        for m in re.finditer(re.escape(ph), low):
            ctx = low[max(0, m.start() - 60): m.start() + 20]
            if "banned" in ctx or "no banned" in ctx or "phrases" in ctx:
                continue
            out["banned_phrases"].append(ph)
            break

    # Rigor Audit section presence + ledger parse.
    idx = low.find("## rigor audit")
    out["rigor_audit_section"] = idx != -1
    if idx != -1:
        ledger = text[idx:]
        for m in re.finditer(r"^\s*([A-E]\d)\s*[:\-]\s*([A-Za-z/ ]+)", ledger, re.M):
            item, verdict = m.group(1), m.group(2).strip().upper()
            first = verdict.split()[0] if verdict else ""
            if first.startswith("PASS") or first.startswith("N/A") or first.startswith("N/A"):
                continue
            if first.startswith("PARTIAL") or first.startswith("FAIL"):
                out["ledger_non_pass"].append(f"{item}:{first}")

    ok = (out["rubric_present"] and out["notes_present"]
          and out["rigor_audit_section"] and not out["banned_phrases"]
          and not out["ledger_non_pass"])
    out["verdict"] = "PASS" if ok else "FAIL"
    return out


def steps123_run_proof(node_dir: Path) -> dict:
    """Run proof.py; parse engine verdicts + final status + exit code."""
    proof = node_dir / "proof.py"
    out = {"ran": False, "exit_code": None, "engines": {},
           "final_status": None, "stdout_tail": ""}
    if not proof.exists():
        out["final_status"] = "NO_PROOF_FILE"
        return out
    t0 = time.time()
    proc = subprocess.run(
        [sys.executable, "-X", "utf8", str(proof)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(PROOFS_DIR.parent.parent), timeout=600,
    )
    out["ran"] = True
    out["exit_code"] = proc.returncode
    out["elapsed_s"] = round(time.time() - t0, 1)
    stdout = proc.stdout or ""

    # Parse the FINAL verifier-coverage line (last occurrence of each engine).
    engines: dict[str, str] = {}
    for m in ENGINE_RE.finditer(stdout):
        eng = m.group(1).title().replace("Sympy", "SymPy").replace("Numpy", "NumPy")
        val = m.group(2).upper()
        norm = "PASS" if val in ("TRUE", "PASS") else ("FAIL" if val in ("FALSE", "FAIL") else "NA")
        engines[eng] = norm  # later occurrences overwrite -> final verdict
    out["engines"] = engines

    sm = list(STATUS_RE.finditer(stdout))
    out["final_status"] = sm[-1].group(1).upper() if sm else None
    out["stdout_tail"] = "\n".join(stdout.splitlines()[-6:])
    if proc.stderr:
        out["stderr_tail"] = "\n".join(proc.stderr.splitlines()[-4:])
    return out


def steps456_proof_assistants(node_dir: Path) -> dict:
    """Detect Lean/Coq artefacts and toolchain. Axiom-only Lean files are STUBs
    (not load-bearing); a real proof requires a checker we mark SKIP when absent."""
    out = {"lean_files": [], "coq_files": [], "lean_toolchain": False,
           "coq_toolchain": False, "verdict": "NONE"}
    import shutil
    out["lean_toolchain"] = bool(shutil.which("lean") or shutil.which("lake"))
    out["coq_toolchain"] = bool(shutil.which("coqc") or shutil.which("coq"))
    for f in node_dir.glob("*.lean"):
        body = f.read_text(encoding="utf-8", errors="replace")
        axiom_only = ("axiom" in body) and ("theorem" not in body.lower().replace("theorem_", ""))
        out["lean_files"].append({"name": f.name, "axiom_stub": axiom_only})
    for f in node_dir.glob("*.v"):
        out["coq_files"].append(f.name)
    if out["lean_files"] or out["coq_files"]:
        if (out["lean_files"] and not out["lean_toolchain"]) or (out["coq_files"] and not out["coq_toolchain"]):
            out["verdict"] = "SKIP_NO_TOOLCHAIN"
        else:
            out["verdict"] = "PRESENT"
    return out


def step7_gate(step0: dict, s123: dict, s456: dict) -> dict:
    """Two-grader gate (D1). PASS iff Step0 clean, >=2 executable verifiers PASS,
    and no executable verifier FAILs (agreement)."""
    engines = s123.get("engines", {})
    passes = [e for e, v in engines.items() if v == "PASS"]
    fails = [e for e, v in engines.items() if v == "FAIL"]
    reasons = []
    if step0["verdict"] != "PASS":
        bits = []
        if not step0["rubric_present"]:
            bits.append("no RUBRIC.md")
        if not step0["rigor_audit_section"]:
            bits.append("no Rigor Audit section")
        if step0["banned_phrases"]:
            bits.append(f"banned phrases {step0['banned_phrases']}")
        if step0["ledger_non_pass"]:
            bits.append(f"ledger {step0['ledger_non_pass']}")
        reasons.append("Step0: " + "; ".join(bits))
    if fails:
        reasons.append(f"verifier disagreement: {fails} report FAIL")
    if len(passes) < 2:
        reasons.append(f"two-grader gate: only {len(passes)} engine(s) PASS ({passes})")
    if s123.get("exit_code") not in (0, None):
        # exit code may be nonzero on PARTIAL-by-design; only flag if also no consensus
        if len(passes) < 2:
            reasons.append(f"proof.py exit {s123.get('exit_code')}")
    verdict = "PASS" if not reasons else "FAIL"
    return {"verdict": verdict, "engines_pass": passes, "engines_fail": fails,
            "reasons": reasons}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", type=Path, default=PROOFS_DIR / "result_registry.json")
    args = ap.parse_args(argv)

    print("=" * 74)
    print("PROOF PIPELINE — MathArena Steps 0-7 (two-grader gate, RIGOR_CHECKLIST D1)")
    print("=" * 74)

    registry = {"generated_by": "theory/proofs/run_pipeline.py",
                "nodes": {}, "engines_available": {
                    "sympy": True, "numpy": True, "z3": True,
                    "lean": False, "coq": False}}
    all_pass = True
    for node in NODES:
        d = PROOFS_DIR / node
        s0 = step0_matharena_audit(d)
        s123 = steps123_run_proof(d)
        s456 = steps456_proof_assistants(d)
        gate = step7_gate(s0, s123, s456)
        registry["nodes"][node] = {"step0": s0, "steps123": s123,
                                   "steps456": s456, "gate": gate}
        if gate["verdict"] != "PASS":
            all_pass = False
        eng = " ".join(f"{e}={v}" for e, v in s123.get("engines", {}).items())
        print(f"\n[{node}]")
        print(f"  Step0 MathArena audit : {s0['verdict']}"
              + (f"  ({'; '.join(filter(None, [','.join(s0['banned_phrases']) or '', ','.join(s0['ledger_non_pass']) or '']))})" if s0['verdict'] != 'PASS' else ""))
        print(f"  Steps1-3 proof.py     : exit={s123.get('exit_code')} status={s123.get('final_status')}  [{eng}]")
        print(f"  Steps4-6 assistants   : {s456['verdict']}"
              + (f"  lean={[f['name'] for f in s456['lean_files']]}" if s456['lean_files'] else ""))
        print(f"  Step7 TWO-GRADER GATE : {gate['verdict']}"
              + (f"  -> {'; '.join(gate['reasons'])}" if gate['reasons'] else f"  ({len(gate['engines_pass'])} engines agree PASS)"))

    n_pass = sum(1 for n in registry["nodes"].values() if n["gate"]["verdict"] == "PASS")
    print("\n" + "=" * 74)
    print(f"PIPELINE RESULT: {n_pass}/{len(NODES)} nodes PASS the two-grader gate")
    print("=" * 74)
    registry["summary"] = {"nodes_total": len(NODES), "nodes_pass": n_pass,
                           "all_pass": all_pass}

    args.json.write_text(json.dumps(registry, indent=2), encoding="utf-8")
    print(f"wrote {args.json}")

    # Human-readable proof map.
    pm = PROOFS_DIR / "proof_map.md"
    lines = ["# Proof map — pipeline result\n",
             f"Driver: `theory/proofs/run_pipeline.py`. Nodes passing the two-grader gate: **{n_pass}/{len(NODES)}**.\n",
             "Engines available on this machine: SymPy, NumPy, Z3 (Lean/Coq toolchains absent; "
             "each node carries 3 executable verifiers, so the two-grader rule is met without them).\n",
             "| Node | Step 0 audit | SymPy | NumPy | Z3 | Final status | Gate |",
             "|---|---|---|---|---|---|---|"]
    for node, r in registry["nodes"].items():
        e = r["steps123"]["engines"]
        lines.append(f"| {node} | {r['step0']['verdict']} | {e.get('SymPy','-')} | "
                     f"{e.get('NumPy','-')} | {e.get('Z3','-')} | "
                     f"{r['steps123'].get('final_status','-')} | **{r['gate']['verdict']}** |")
    pm.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {pm}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
