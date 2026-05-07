"""Experiment 2: trial-level correlation between probe score and compliance.

For each TOOL_DIRECT trial, extract the layer-N probe logit ("channel-authority score")
and pair it with the binary judge_harmful_execution label from the Llama-3 trial JSON
(produced by run_subject_local.py + the re-judge step). Report Pearson r and
Spearman rho with bootstrap 95% CIs, plus AUC for compliance ~ probe-score classifier.

Sanity check: does the probe score predict compliance on USER_IMPERATIVE trials too?
If the channel-authority direction is specifically tied to the tool-channel's effect
on compliance, the correlation should be weaker on user-imperative trials.

Reads outputs/probes/probe_layer_<best>.pkl (chosen via outputs/exp1_results.json) and
outputs/llama_trials/*.json. Outputs outputs/exp2_results.json.
"""

from __future__ import annotations

import argparse
import json
import pickle
from pathlib import Path

import numpy as np
from scipy.stats import pearsonr, spearmanr
from sklearn.metrics import roc_auc_score

from config import ACTIVATIONS_DIR, LLAMA_TRIALS_DIR, OUTPUTS_DIR, PROBES_DIR


def bootstrap_ci(values: np.ndarray, statistic, n_boot: int = 1000, seed: int = 42) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    n = len(values)
    boot = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, size=n)
        boot.append(statistic(values[idx]))
    return float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))


def load_probe(layer: int):
    with (PROBES_DIR / f"probe_layer_{layer:02d}.pkl").open("rb") as fh:
        bundle = pickle.load(fh)
    return bundle["clf"]


def collect(layer: int) -> dict[str, list]:
    out = {"pair_id": [], "condition": [], "scenario_id": [], "domain": [],
           "compliance": []}
    for trial_path in sorted(LLAMA_TRIALS_DIR.glob("*.json")):
        with trial_path.open(encoding="utf-8") as fh:
            t = json.load(fh)
        pair_id = t["pair_id"]
        condition = t["condition"]
        compliance = t.get("judge_harmful_execution")
        if compliance is None:
            continue
        act_path = ACTIVATIONS_DIR / f"{pair_id}__{condition}.npz"
        if not act_path.exists():
            continue
        npz = np.load(act_path)
        if f"layer_{layer}" not in npz.files:
            continue
        act = npz[f"layer_{layer}"]
        out["pair_id"].append(pair_id)
        out["condition"].append(condition)
        out["scenario_id"].append(t["scenario_id"])
        out["domain"].append(t.get("domain") or t["scenario_id"].split("_")[0])
        out["compliance"].append(int(bool(compliance)))
    return out


def score_with_probe(records: dict, layer: int, clf) -> np.ndarray:
    pair_ids = records["pair_id"]
    conditions = records["condition"]
    scores = []
    for pid, cond in zip(pair_ids, conditions):
        act_path = ACTIVATIONS_DIR / f"{pid}__{cond}.npz"
        npz = np.load(act_path)
        x = npz[f"layer_{layer}"].reshape(1, -1)
        # Use decision_function so we get a continuous "channel-authority score";
        # positive means classified as TOOL_DIRECT.
        scores.append(float(clf.decision_function(x)[0]))
    return np.asarray(scores)


def per_condition_metrics(scores: np.ndarray, compliance: np.ndarray) -> dict:
    if len(scores) < 4 or len(np.unique(compliance)) < 2:
        return {"n": int(len(scores)), "pearson_r": None, "spearman_rho": None, "auc": None}
    r, _ = pearsonr(scores, compliance)
    rho, _ = spearmanr(scores, compliance)
    auc = roc_auc_score(compliance, scores)
    return {"n": int(len(scores)), "pearson_r": float(r), "spearman_rho": float(rho), "auc": float(auc)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--layer", type=int, default=None)
    args = parser.parse_args()

    exp1_path = OUTPUTS_DIR / "exp1_results.json"
    if args.layer is None:
        if not exp1_path.exists():
            raise FileNotFoundError("Run exp1_linear_probe.py first or pass --layer.")
        with exp1_path.open(encoding="utf-8") as fh:
            exp1 = json.load(fh)
        layer = int(exp1["best_layer"])
    else:
        layer = args.layer
    print(f"Using layer {layer} for probe scoring.")

    clf = load_probe(layer)
    records = collect(layer)
    if not records["pair_id"]:
        raise RuntimeError("No trials found with judge_harmful_execution; re-judge first.")

    scores = score_with_probe(records, layer, clf)
    compliance = np.asarray(records["compliance"])
    conditions = np.asarray(records["condition"])

    results = {"layer": layer, "n_total": int(len(scores)),
               "pooled": per_condition_metrics(scores, compliance),
               "tool_direct_only": per_condition_metrics(scores[conditions == "TOOL_DIRECT"],
                                                        compliance[conditions == "TOOL_DIRECT"]),
               "user_imperative_only": per_condition_metrics(scores[conditions == "USER_IMPERATIVE"],
                                                             compliance[conditions == "USER_IMPERATIVE"])}

    if results["tool_direct_only"]["pearson_r"] is not None:
        td_idx = np.where(conditions == "TOOL_DIRECT")[0]
        td_scores = scores[td_idx]
        td_compl = compliance[td_idx]

        def auc_stat(idx):
            sub_scores = td_scores[idx]
            sub_compl = td_compl[idx]
            if len(np.unique(sub_compl)) < 2:
                return 0.5
            return roc_auc_score(sub_compl, sub_scores)

        idx_arr = np.arange(len(td_idx))
        ci_low, ci_high = bootstrap_ci(idx_arr, auc_stat, n_boot=1000, seed=42)
        results["tool_direct_only"]["auc_95ci"] = [ci_low, ci_high]

    out_path = OUTPUTS_DIR / "exp2_results.json"
    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2)
    print(f"Wrote {out_path}")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
