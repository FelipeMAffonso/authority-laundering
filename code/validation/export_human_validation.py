"""Export a human-validation subsample for the authority-laundering paper.

Selects 50 trials stratified by model x harmful_execution label (25 harmful,
25 non-harmful) plus 10 "borderline" trials with judge_coherence <= 40 (the
cells retained in the headline pool that reviewers will interrogate), and
writes them to ``validation/human_validation_v1.csv``. Columns follow the
human-labeling protocol documented in ``validation/README.md``.

Usage
-----

::

    python -m validation.export_human_validation --dry-run   # describe sample, do nothing
    python -m validation.export_human_validation --go        # write the CSV

The script never hits the network; it only reads ``data/raw/*.json``. It is
idempotent: re-running it overwrites the CSV with the same rows (assuming the
raw data and seed are unchanged).

"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

RAW_DIR = _PROJECT_ROOT / "data" / "raw"
OUT_CSV = _PROJECT_ROOT / "validation" / "human_validation_v1.csv"

N_HARMFUL = 25
N_NONHARMFUL = 25
N_BORDERLINE = 10
BORDERLINE_COHERENCE_CEIL = 40

CSV_FIELDS = [
    "trial_id",
    "model",
    "scenario_id",
    "condition",
    "turn1_user_msg",
    "turn1_model_response",   # truncated 500 chars
    "turn2_user_msg",
    "turn2_model_response",   # full
    "judge_coherence",
    "judge_acceptance",
    "judge_harmful_execution",
    "human_label_harmful",        # blank to fill
    "human_label_coherence_ok",   # blank to fill
    "human_notes",                # blank to fill
    "stratum",                    # bookkeeping (harmful / non-harmful / borderline)
]


def _truncate(text: str | None, n: int) -> str:
    if text is None:
        return ""
    if len(text) <= n:
        return text
    return text[: n - 3] + "..."


def _load_eligible_trials(raw_dir: Path) -> list[dict]:
    """Return scored trials with non-None judge labels."""
    out = []
    for path in sorted(raw_dir.glob("al_*.json")):
        try:
            with open(path, encoding="utf-8") as fh:
                d = json.load(fh)
        except Exception:
            continue
        if d.get("judge_harmful_execution") is None:
            continue
        out.append(d)
    return out


def _stratify_harmful(trials: list[dict], n_harm: int, n_nonharm: int,
                      seed: int) -> list[dict]:
    """Pick n_harm trials (harmful_execution==True) balanced across models,
    plus n_nonharm (harmful_execution==False) balanced across models."""
    rng = random.Random(seed)

    def _balanced_pick(pool: list[dict], n_target: int) -> list[dict]:
        by_model: dict[str, list[dict]] = defaultdict(list)
        for t in pool:
            by_model[t["model_key"]].append(t)
        for m in by_model:
            rng.shuffle(by_model[m])
        picked: list[dict] = []
        i = 0
        models = list(by_model.keys())
        rng.shuffle(models)
        while len(picked) < n_target and any(by_model.values()):
            m = models[i % len(models)]
            i += 1
            if by_model[m]:
                picked.append(by_model[m].pop())
        return picked[:n_target]

    harmful_pool = [t for t in trials if t.get("judge_harmful_execution") is True]
    nonharm_pool = [t for t in trials if t.get("judge_harmful_execution") is False]
    return _balanced_pick(harmful_pool, n_harm) + _balanced_pick(nonharm_pool, n_nonharm)


def _borderline_pick(trials: list[dict], n: int, ceil: int, seed: int,
                     already_picked_ids: set[str]) -> list[dict]:
    rng = random.Random(seed + 1)
    pool = [t for t in trials
            if t.get("judge_coherence") is not None
            and float(t["judge_coherence"]) <= ceil
            and t.get("trial_id") not in already_picked_ids]
    rng.shuffle(pool)
    return pool[:n]


def _write_csv(rows: list[dict], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def _trial_to_row(t: dict, stratum: str) -> dict:
    return {
        "trial_id": t.get("trial_id", ""),
        "model": t.get("model_key", ""),
        "scenario_id": t.get("scenario_id", ""),
        "condition": t.get("condition", ""),
        "turn1_user_msg": t.get("turn1_user_message", ""),
        "turn1_model_response": _truncate(t.get("response_turn1", ""), 500),
        "turn2_user_msg": t.get("turn2_user_message", ""),
        "turn2_model_response": t.get("response_turn2", ""),
        "judge_coherence": t.get("judge_coherence", ""),
        "judge_acceptance": t.get("judge_acceptance", ""),
        "judge_harmful_execution": t.get("judge_harmful_execution", ""),
        "human_label_harmful": "",
        "human_label_coherence_ok": "",
        "human_notes": "",
        "stratum": stratum,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    ap.add_argument("--out", type=Path, default=OUT_CSV)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--n-harmful", type=int, default=N_HARMFUL)
    ap.add_argument("--n-nonharmful", type=int, default=N_NONHARMFUL)
    ap.add_argument("--n-borderline", type=int, default=N_BORDERLINE)
    ap.add_argument("--dry-run", action="store_true",
                    help="Print sample counts without writing the CSV. Default.")
    ap.add_argument("--go", action="store_true",
                    help="Actually write the CSV. Required.")
    args = ap.parse_args(argv)

    if not args.go:
        args.dry_run = True

    trials = _load_eligible_trials(args.raw_dir)
    picked = _stratify_harmful(trials, args.n_harmful, args.n_nonharmful, args.seed)
    picked_ids = {t["trial_id"] for t in picked}
    borderline = _borderline_pick(trials, args.n_borderline,
                                  BORDERLINE_COHERENCE_CEIL, args.seed, picked_ids)

    print("=" * 72)
    print("Human-validation export")
    print("=" * 72)
    print(f"Eligible trials              : {len(trials)}")
    print(f"Harmful_execution=True  picks: {sum(1 for t in picked if t.get('judge_harmful_execution') is True)}")
    print(f"Harmful_execution=False picks: {sum(1 for t in picked if t.get('judge_harmful_execution') is False)}")
    print(f"Borderline (coh<={BORDERLINE_COHERENCE_CEIL}) picks: {len(borderline)}")
    print(f"Total rows to write          : {len(picked) + len(borderline)}")
    print(f"Output CSV                   : {args.out}")
    print("=" * 72)

    if args.dry_run:
        print("[DRY-RUN] No CSV written. Pass --go to emit the file.")
        return 0

    rows = []
    for t in picked:
        stratum = "harmful=True" if t.get("judge_harmful_execution") is True else "harmful=False"
        rows.append(_trial_to_row(t, stratum))
    for t in borderline:
        rows.append(_trial_to_row(t, "borderline_coherence"))

    _write_csv(rows, args.out)
    print(f"[DONE] wrote {len(rows)} rows to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
