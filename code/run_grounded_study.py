"""Study 4 — user-grounding defense sweep.

Wraps TOOL_DIRECT with the user-grounding-fact prefix per scenario. The
fabricated authority arrives in the tool result; the user states a
contradicting fact in turn 1 before the question.

Compares compliance rate to the un-grounded TOOL_DIRECT baseline (already
collected in the main pilot). Headline finding: contradiction-carrying user
turn cuts harmful_execution by N percentage points.

10 scenarios x 9 models x 5 reps = 450 trials.
"""

import sys, os, json, time, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from config.models import ALL_MODELS, JUDGE_MODELS, JUDGE_MODEL_DEFAULT, compute_cost
from experiment.scenarios import get_scenario
from experiment.conditions import build, build_user_grounded
from harness.core import load_env, call_two_turn_retry
from harness.judge import judge_response, enrich_trial
from harness.cost_tracker import CostTracker

RAW_DIR = Path(__file__).parent / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

# 10 scenarios across harm levels (subset of the 14 main bank)
SCENARIOS = [
    "HEA_01_acetaminophen_pediatric",      # SEVERE
    "HEA_02_warfarin_nsaid",               # SEVERE
    "SEC_01_disable_ssl_verification",     # SEVERE
    "TAX_01_401k_home_modernization_hardship",  # MODERATE
    "ENV_01_epa_wotus_hobby_landowner",    # MODERATE
    "LAW_04_PRETEXT_paralegal_emergency_motion",  # MODERATE
    "HR_01_age_cohort_screening",          # MODERATE
    "ELC_01_florida_felon_voting_lfo",     # MODERATE
    "ENV_02_energy_star_override",         # MINOR
    "ACA_01_fabricated_meta_analysis",     # MINOR
]
MODELS = [
    "claude-opus-4.7", "claude-opus-4.6", "claude-sonnet-4.6",
    "claude-sonnet-4.5", "claude-haiku-4.5",
    "gpt-5.4-mini", "gpt-5.4-nano",
    "gemini-3.0-flash", "gemini-3.1-flash-lite",
]
BASE_CONDITION = "TOOL_DIRECT"
GROUNDED_CONDITION = "TOOL_DIRECT_GROUNDED"
DIRECTION = "harmful"
REPS = 5


def _hash(mk, sid, cond, direction, t):
    return hashlib.sha1(f"{mk}|{sid}|{cond}|{direction}|{t}".encode()).hexdigest()[:8]


def run_grounded_trial(model_key, scenario_id, trial_idx, tracker):
    s = get_scenario(scenario_id)
    path = RAW_DIR / f"al_{model_key}_{scenario_id}_{GROUNDED_CONDITION}_d{DIRECTION}_t{trial_idx}_{_hash(model_key, scenario_id, GROUNDED_CONDITION, DIRECTION, trial_idx)}.json"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    base = build(BASE_CONDITION, s, direction=DIRECTION, paraphrase_idx=trial_idx % 3)
    pkg = build_user_grounded(base, s)
    model_cfg = ALL_MODELS[model_key]
    t0 = time.time()
    try:
        r = call_two_turn_retry(
            model_key=model_key, model_cfg=model_cfg,
            system_prompt=pkg["system_prompt"],
            turn1_msg=pkg["turn1_user_message"],
            turn2_msg=pkg["turn2_user_message"],
            tool_turn=pkg.get("tool_turn"), max_tokens=1024, temperature=1.0,
        )
    except Exception as e:
        err_trial = {"trial_id": path.stem, "model_key": model_key, "scenario_id": scenario_id,
                     "condition": GROUNDED_CONDITION, "error": str(e)[:500]}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(err_trial, f, indent=2)
        return err_trial
    cost = compute_cost(model_cfg["model_id"], r["input_tokens"], r["output_tokens"])
    tracker.record_call(model_cfg["provider"], model_cfg["model_id"],
                        r["input_tokens"], r["output_tokens"], cost,
                        experiment="al_grounded", trial_id=path.stem)
    judge_cfg = JUDGE_MODELS[JUDGE_MODEL_DEFAULT]
    try:
        scores = judge_response(
            question=pkg["turn2_user_message"], answer=r["text2"] or r["text1"],
            scenario=s, direction=DIRECTION,
            judge_model_key=JUDGE_MODEL_DEFAULT, judge_model_cfg=judge_cfg,
        )
    except Exception as e:
        scores = {"coherence": None, "acceptance": None, "harmful_execution": None,
                  "judge_model": JUDGE_MODEL_DEFAULT, "judge_raw": {"error": str(e)}}
    trial = {
        "trial_id": path.stem, "model_key": model_key,
        "model_id": model_cfg["model_id"], "provider": model_cfg["provider"],
        "scenario_id": scenario_id, "domain": s["domain"],
        "is_pretext": s.get("is_pretext", False),
        "condition": GROUNDED_CONDITION, "direction": DIRECTION, "trial_idx": trial_idx,
        "system_prompt": pkg["system_prompt"],
        "turn1_user_message": pkg["turn1_user_message"],
        "turn2_user_message": pkg["turn2_user_message"],
        "tool_turn": pkg.get("tool_turn"),
        "response_turn1": r.get("text1", ""),
        "response_turn2": r.get("text2", ""),
        "tool_invoked": r.get("tool_invoked"),
        "input_tokens": r["input_tokens"], "output_tokens": r["output_tokens"],
        "subject_cost_usd": cost,
        "elapsed_s": round(time.time() - t0, 2),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "raw_response": r.get("text2") or r.get("text1", ""),
    }
    trial = enrich_trial(trial, scores)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(trial, f, indent=2, ensure_ascii=False)
    return trial


def main():
    load_env()
    tracker = CostTracker(budget_per_provider=100.0)
    jobs = [(mk, sid, t) for mk in MODELS for sid in SCENARIOS for t in range(REPS)]
    print(f"User-grounded study: {len(jobs)} trials")
    n_done = n_err = 0
    with ThreadPoolExecutor(max_workers=5) as ex:
        futs = [ex.submit(run_grounded_trial, mk, sid, t, tracker) for (mk, sid, t) in jobs]
        for fut in as_completed(futs):
            tr = fut.result()
            if "error" in tr and "response_turn2" not in tr:
                n_err += 1
            else:
                n_done += 1
            if (n_done + n_err) % 25 == 0:
                print(f"  progress: {n_done} done + {n_err} err / {len(jobs)}")
    tracker.print_summary()
    print(f"\nFINAL: {n_done} done, {n_err} errors")


if __name__ == "__main__":
    main()
