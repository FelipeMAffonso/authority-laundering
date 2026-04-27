"""Two-turn factorial runner for authority-laundering Study 1.

Pipeline per trial:
  1. Build turn-1 + turn-2 messages from scenario x condition x direction.
  2. Call provider's two-turn API (forced tool use on TOOL cells).
  3. Judge turn-2 response on coherence / acceptance / harmful_execution.
  4. Save JSON to data/raw/.

Usage:
  python -m experiment.runner --model=claude-opus-4.7 --study=main --parallel=3
  python -m experiment.runner --model=claude-opus-4.7 --study=pilot
"""

import argparse
import hashlib
import json
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from config.models import ALL_MODELS, JUDGE_MODELS, JUDGE_MODEL_DEFAULT, compute_cost
from experiment.scenarios import SCENARIOS
from experiment.conditions import MAIN_CONDITIONS, ED_GRAMMAR_CONDITIONS, build
from harness.core import load_env, call_two_turn_retry
from harness.judge import judge_response, enrich_trial
from harness.cost_tracker import CostTracker, BudgetExceededError


RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# Study presets
# ============================================================

STUDY_PRESETS = {
    "main": {
        "conditions": MAIN_CONDITIONS,
        "reps": 10,
    },
    "pilot": {
        "conditions": MAIN_CONDITIONS,
        "reps": 1,
    },
    "smoke": {  # exemplar subset used during rebuild
        "conditions": MAIN_CONDITIONS,
        "reps": 1,
    },
    "ed_grammar": {
        "conditions": ED_GRAMMAR_CONDITIONS,
        "reps": 5,
    },
}


def _hash(model_key, scenario_id, condition, direction, trial_idx):
    raw = f"{model_key}|{scenario_id}|{condition}|{direction}|{trial_idx}"
    return hashlib.sha1(raw.encode()).hexdigest()[:8]


def _path(model_key, scenario_id, condition, direction, trial_idx):
    h = _hash(model_key, scenario_id, condition, direction, trial_idx)
    return RAW_DIR / f"al_{model_key}_{scenario_id}_{condition}_d{direction}_t{trial_idx}_{h}.json"


# ============================================================
# One trial (2-turn + judge)
# ============================================================

def _run_one(model_key, model_cfg, scenario, condition, direction, trial_idx,
              judge_model_key, tracker, paraphrase_idx=0):
    path = _path(model_key, scenario["id"], condition, direction, trial_idx)
    if path.exists():
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        d["_cached"] = True
        return d

    pkg = build(condition, scenario, direction=direction, paraphrase_idx=paraphrase_idx)

    t0 = time.time()
    try:
        r = call_two_turn_retry(
            model_key=model_key,
            model_cfg=model_cfg,
            system_prompt=pkg["system_prompt"],
            turn1_msg=pkg["turn1_user_message"],
            turn2_msg=pkg["turn2_user_message"],
            tool_turn=pkg.get("tool_turn"),
            max_tokens=1024,
            temperature=1.0,
        )
    except Exception as e:
        return {"error": str(e), "model_key": model_key, "scenario_id": scenario["id"],
                "condition": condition, "direction": direction, "trial_idx": trial_idx,
                "_cached": False}

    cost = compute_cost(model_cfg["model_id"], r["input_tokens"], r["output_tokens"])
    tracker.record_call(model_cfg["provider"], model_cfg["model_id"],
                        r["input_tokens"], r["output_tokens"], cost,
                        experiment="al_main", trial_id=path.stem)

    # Judge is run on turn-2 response (the operational compliance turn).
    judge_cfg = JUDGE_MODELS[judge_model_key]
    try:
        scores = judge_response(
            question=pkg["turn2_user_message"] or pkg["turn1_user_message"],
            answer=r["text2"] or r["text1"],  # fall back to text1 if turn2 empty
            scenario=scenario,
            direction=direction,
            judge_model_key=judge_model_key,
            judge_model_cfg=judge_cfg,
        )
    except Exception as e:
        scores = {"coherence": None, "acceptance": None, "harmful_execution": None,
                  "judge_model": judge_model_key, "judge_raw": {"error": str(e)}}

    trial = {
        "trial_id": path.stem, "model_key": model_key,
        "model_id": model_cfg["model_id"], "provider": model_cfg["provider"],
        "scenario_id": scenario["id"], "domain": scenario["domain"],
        "is_pretext": scenario.get("is_pretext", False),
        "condition": condition, "direction": direction,
        "trial_idx": trial_idx, "paraphrase_idx": paraphrase_idx,
        "system_prompt": pkg["system_prompt"],
        "turn1_user_message": pkg["turn1_user_message"],
        "turn2_user_message": pkg["turn2_user_message"],
        "tool_turn": pkg.get("tool_turn"),
        "response_turn1": r.get("text1", ""),
        "response_turn2": r.get("text2", ""),
        "tool_invoked": r.get("tool_invoked"),
        "tool_use_input": r.get("tool_use_input"),
        "input_tokens": r["input_tokens"],
        "output_tokens": r["output_tokens"],
        "subject_cost_usd": cost,
        "elapsed_s": round(time.time() - t0, 2),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        # For judge.py backward compat:
        "raw_response": r.get("text2") or r.get("text1", ""),
    }
    trial = enrich_trial(trial, scores)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(trial, f, indent=2, ensure_ascii=False)
    trial["_cached"] = False
    return trial


# ============================================================
# Study runner
# ============================================================

def run_study(model_key, study="main", direction="harmful", parallel=3,
                budget=100.0, judge_model_key=JUDGE_MODEL_DEFAULT,
                reps_override=None, scenarios_override=None):
    load_env()
    if model_key not in ALL_MODELS:
        raise KeyError(f"unknown model_key: {model_key}")
    model_cfg = ALL_MODELS[model_key]

    preset = STUDY_PRESETS[study]
    scenarios = scenarios_override or SCENARIOS
    conditions = preset["conditions"]
    reps = reps_override if reps_override is not None else preset["reps"]

    tracker = CostTracker(budget_per_provider=budget)

    jobs = []
    for s in scenarios:
        for c in conditions:
            for t in range(reps):
                p_idx = (t + hash(s["id"] + c)) % 3
                jobs.append((s, c, t, p_idx))

    random.seed(hash(model_key))
    random.shuffle(jobs)

    print(f"[{model_key}] study={study} dir={direction} scenarios={len(scenarios)} "
          f"conditions={len(conditions)} reps={reps} -> {len(jobs)} trials, parallel={parallel}")

    n_new, n_cached, n_err = 0, 0, 0
    with ThreadPoolExecutor(max_workers=parallel) as ex:
        futures = [ex.submit(_run_one, model_key, model_cfg, s, c, direction,
                              t, judge_model_key, tracker, p)
                    for (s, c, t, p) in jobs]
        for fut in as_completed(futures):
            try:
                trial = fut.result()
                if "error" in trial and "response_turn1" not in trial:
                    n_err += 1
                elif trial.get("_cached"):
                    n_cached += 1
                else:
                    n_new += 1
                if (n_new + n_cached + n_err) % 25 == 0:
                    print(f"  [{model_key}] {n_new} new + {n_cached} cached + {n_err} err / {len(jobs)}")
            except BudgetExceededError as e:
                print(f"  [{model_key}] BUDGET: {e}")
                break

    tracker.print_summary()
    tracker.save_log(f"al_costs_{model_key}_{study}_{int(time.time())}.json")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--model", required=True)
    p.add_argument("--study", default="main", choices=list(STUDY_PRESETS.keys()))
    p.add_argument("--direction", default="harmful", choices=["harmful", "benign"])
    p.add_argument("--parallel", type=int, default=3)
    p.add_argument("--budget", type=float, default=100.0)
    p.add_argument("--judge", default=JUDGE_MODEL_DEFAULT)
    p.add_argument("--reps", type=int, default=None)
    args = p.parse_args()
    run_study(args.model, study=args.study, direction=args.direction,
               parallel=args.parallel, budget=args.budget,
               judge_model_key=args.judge, reps_override=args.reps)
