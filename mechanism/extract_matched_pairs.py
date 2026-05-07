"""Pull matched (TOOL_DIRECT, USER_IMPERATIVE) pairs from data/raw/ for the mechanism work.

A matched pair is two trials on the same scenario, same trial_idx, same direction,
that differ only in delivery channel. The source model is configurable in config.py
(default: llama-4-scout, the closest open-weight subject in the existing panel). The
prompts from those trials become the input stimuli for re-running on Llama 3.1 8B
with activation capture.

Outputs outputs/matched_pairs.jsonl, one line per pair, with both sides' prompt
elements and the closed-panel reference compliance labels.

Usage:
    python extract_matched_pairs.py
    python extract_matched_pairs.py --source-model gpt-oss-120b --include-direction benign
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from config import RAW_DATA_DIR, OUTPUTS_DIR, SOURCE_MODEL_KEY, CONDITIONS, DIRECTIONS


def load_trial(path: Path) -> dict | None:
    try:
        with path.open(encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        return None


def trial_key(trial: dict) -> tuple[str, str, int]:
    return (trial["scenario_id"], trial["direction"], trial["trial_idx"])


def collect_trials(source_model: str, conditions: list[str], directions: list[str]) -> dict:
    """Return {(scenario_id, direction, trial_idx): {condition: trial}}."""
    grouped: dict[tuple[str, str, int], dict[str, dict]] = defaultdict(dict)
    n_scanned = 0
    n_kept = 0
    for path in RAW_DATA_DIR.glob(f"al_{source_model}_*.json"):
        n_scanned += 1
        trial = load_trial(path)
        if trial is None:
            continue
        if trial.get("model_key") != source_model:
            continue
        if trial.get("condition") not in conditions:
            continue
        if trial.get("direction") not in directions:
            continue
        if trial.get("response_turn2") is None:
            continue
        key = trial_key(trial)
        grouped[key][trial["condition"]] = trial
        n_kept += 1
    print(f"Scanned {n_scanned} files for source_model={source_model}; kept {n_kept} usable trials.")
    return grouped


def build_pair_record(key: tuple[str, str, int], trials: dict[str, dict]) -> dict:
    scenario_id, direction, trial_idx = key
    tool = trials["TOOL_DIRECT"]
    user = trials["USER_IMPERATIVE"]
    return {
        "pair_id": f"{scenario_id}__{direction}__t{trial_idx}",
        "scenario_id": scenario_id,
        "domain": tool.get("domain") or user.get("domain"),
        "direction": direction,
        "trial_idx": trial_idx,
        "tool_direct": {
            "trial_id": tool["trial_id"],
            "system_prompt": tool["system_prompt"],
            "turn1_user_message": tool["turn1_user_message"],
            "turn2_user_message": tool["turn2_user_message"],
            "tool_turn": tool.get("tool_turn"),
            "response_turn1": tool.get("response_turn1"),
            "response_turn2": tool.get("response_turn2"),
            "judge_harmful_execution": tool.get("judge_harmful_execution"),
        },
        "user_imperative": {
            "trial_id": user["trial_id"],
            "system_prompt": user["system_prompt"],
            "turn1_user_message": user["turn1_user_message"],
            "turn2_user_message": user["turn2_user_message"],
            "tool_turn": user.get("tool_turn"),
            "response_turn1": user.get("response_turn1"),
            "response_turn2": user.get("response_turn2"),
            "judge_harmful_execution": user.get("judge_harmful_execution"),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-model", default=SOURCE_MODEL_KEY)
    parser.add_argument("--include-direction", choices=["harmful", "benign", "both"], default="harmful")
    parser.add_argument("--out", default=str(OUTPUTS_DIR / "matched_pairs.jsonl"))
    args = parser.parse_args()

    directions = ["harmful"] if args.include_direction == "harmful" else (
        ["benign"] if args.include_direction == "benign" else ["harmful", "benign"]
    )

    grouped = collect_trials(args.source_model, CONDITIONS, directions)

    pairs = []
    n_complete = 0
    n_partial = 0
    for key, trials in grouped.items():
        if all(c in trials for c in CONDITIONS):
            pairs.append(build_pair_record(key, trials))
            n_complete += 1
        else:
            n_partial += 1

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        for pair in pairs:
            fh.write(json.dumps(pair, ensure_ascii=False) + "\n")

    by_scenario: dict[str, int] = defaultdict(int)
    by_domain: dict[str, int] = defaultdict(int)
    for p in pairs:
        by_scenario[p["scenario_id"]] += 1
        by_domain[p["domain"] or "unknown"] += 1

    print(f"\nWrote {n_complete} complete pairs to {out_path}")
    print(f"Skipped {n_partial} partial groups (only one condition collected)")
    print(f"\nPairs by scenario ({len(by_scenario)} scenarios):")
    for sid, n in sorted(by_scenario.items(), key=lambda kv: -kv[1]):
        print(f"  {sid:50s} {n}")
    print(f"\nPairs by domain ({len(by_domain)} domains):")
    for dom, n in sorted(by_domain.items(), key=lambda kv: -kv[1]):
        print(f"  {dom:20s} {n}")


if __name__ == "__main__":
    main()
