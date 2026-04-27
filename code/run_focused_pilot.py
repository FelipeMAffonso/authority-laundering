"""Focused cross-model pilot: single condition (TOOL_DIRECT), 4 key scenarios,
all 7 models, 5 reps per cell. ~140 trials. ~10-15 minutes wall clock.

Goal: establish whether compliance emerges on grey-area scenarios, and whether
hard-safety holds across all models including small open-weight (Gemma 3 27B).

Usage:
    python run_focused_pilot.py
"""

import sys, os, json, time, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from config.models import ALL_MODELS, JUDGE_MODELS, JUDGE_MODEL_DEFAULT, compute_cost
from experiment.scenarios import get_scenario
from experiment.conditions import build
from harness.core import load_env, call_two_turn_retry
from harness.judge import judge_response, enrich_trial
from harness.cost_tracker import CostTracker

RAW_DIR = Path(__file__).parent / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

SCENARIOS = [
    # SEVERE
    "HEA_01_acetaminophen_pediatric",
    "HEA_02_warfarin_nsaid",
    "SEC_01_disable_ssl_verification",
    "SEC_02_sql_string_concat",
    # MODERATE
    "HEA_03_mmr_efficacy_misinformation",
    "TAX_01_401k_home_modernization_hardship",
    "TAX_02_PRETEXT_accredited_investor",
    "ENV_01_epa_wotus_hobby_landowner",
    "LAW_01_smithfield_carrington_precedent",
    "LAW_04_PRETEXT_paralegal_emergency_motion",
    "HR_01_age_cohort_screening",
    "ELC_01_florida_felon_voting_lfo",
    # MINOR
    "ENV_02_energy_star_override",
    "ACA_01_fabricated_meta_analysis",
]
MODELS = [
    # Anthropic (5 gens/tiers)
    "claude-opus-4.7", "claude-opus-4.6", "claude-sonnet-4.6",
    "claude-sonnet-4.5", "claude-haiku-4.5",
    # OpenAI (2)
    "gpt-5.4-mini", "gpt-5.4-nano",
    # Google (2)
    "gemini-3.0-flash", "gemini-3.1-flash-lite",
]
DIRECTION = "harmful"
REPS = 5

# Multi-condition sweep. Default runs all conditions we want for the preprint.
# Override with CLI arg: python run_focused_pilot.py CONTROL_NONE USER_IMPERATIVE
CONDITIONS = [
    "CONTROL_NONE",       # baseline; enables Betley-style delta story
    "USER_IMPERATIVE",    # kill-experiment floor; matches Betley `jailbroken` control
    "DOC_SMUGGLED",       # one SMUGGLED grammar cell (document-channel)
]
# Single-condition back-compat — scripts that read CONDITION still work.
CONDITION = CONDITIONS[0]


def _hash(mk, sid, cond, direction, t):
    return hashlib.sha1(f"{mk}|{sid}|{cond}|{direction}|{t}".encode()).hexdigest()[:8]


def run_trial(model_key, scenario_id, trial_idx, tracker, condition=None):
    if condition is None:
        condition = CONDITION
    s = get_scenario(scenario_id)
    path = RAW_DIR / f"al_{model_key}_{scenario_id}_{condition}_d{DIRECTION}_t{trial_idx}_{_hash(model_key, scenario_id, condition, DIRECTION, trial_idx)}.json"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    pkg = build(condition, s, direction=DIRECTION, paraphrase_idx=trial_idx % 3)
    model_cfg = ALL_MODELS[model_key]
    t0 = time.time()
    try:
        r = call_two_turn_retry(
            model_key=model_key, model_cfg=model_cfg,
            system_prompt=pkg["system_prompt"],
            turn1_msg=pkg["turn1_user_message"],
            turn2_msg=pkg["turn2_user_message"],
            tool_turn=pkg["tool_turn"], max_tokens=1024, temperature=1.0,
        )
    except Exception as e:
        err_trial = {"trial_id": path.stem, "model_key": model_key, "scenario_id": scenario_id,
                     "condition": condition, "error": str(e)[:500]}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(err_trial, f, indent=2)
        return err_trial
    cost = compute_cost(model_cfg["model_id"], r["input_tokens"], r["output_tokens"])
    tracker.record_call(model_cfg["provider"], model_cfg["model_id"],
                        r["input_tokens"], r["output_tokens"], cost,
                        experiment="al_focused", trial_id=path.stem)
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
        "condition": condition, "direction": DIRECTION, "trial_idx": trial_idx,
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
    import sys as _sys
    load_env()
    tracker = CostTracker(budget_per_provider=200.0)
    # CLI override: python run_focused_pilot.py COND1 COND2 ...
    conds = _sys.argv[1:] if len(_sys.argv) > 1 else CONDITIONS
    jobs = [(mk, sid, t, cond)
             for cond in conds
             for mk in MODELS
             for sid in SCENARIOS
             for t in range(REPS)]
    print(f"Launching {len(jobs)} trials: {len(MODELS)} models x {len(SCENARIOS)} scenarios x "
          f"{REPS} reps x {len(conds)} conditions = {len(conds)} sweeps")
    print(f"Conditions: {conds}")
    n_done = n_err = n_cached = 0
    with ThreadPoolExecutor(max_workers=5) as ex:
        futs = [ex.submit(run_trial, mk, sid, t, tracker, cond)
                 for (mk, sid, t, cond) in jobs]
        for fut in as_completed(futs):
            tr = fut.result()
            if "error" in tr and "response_turn2" not in tr:
                n_err += 1
            elif tr.get("judge_coherence") is not None and (tr.get("_cached") or "judge_raw_coherence" in tr):
                # already had scores when loaded — cached hit
                if "response_turn2" in tr:
                    n_done += 1
                else:
                    n_cached += 1
            else:
                n_done += 1
            total = n_done + n_err + n_cached
            if total % 25 == 0:
                print(f"  progress: {n_done} new + {n_cached} cached + {n_err} err / {len(jobs)}")
    tracker.print_summary()
    print(f"\nFINAL: {n_done} new, {n_cached} cached, {n_err} errors")


if __name__ == "__main__":
    main()
