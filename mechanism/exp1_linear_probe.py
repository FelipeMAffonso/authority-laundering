"""Experiment 1: linear decodability of channel origin from residual-stream activations.

For each transformer layer, train an L2-regularized logistic regression probe to
classify channel-of-origin (TOOL_DIRECT=1 vs USER_IMPERATIVE=0) from the captured
last-token activation. Report probe accuracy as a function of layer depth, with
two cross-validation regimes:

1. Scenario-stratified train/val/test split: probe must generalize to held-out
   scenarios, not just held-out replicates of seen scenarios.
2. Leave-one-domain-out: probe must generalize to held-out domains.

CPU only. Outputs (per --subject suffix):
    outputs/probes_<subject>/probe_layer_<L>.pkl
    outputs/exp1_results_<subject>.json   (full layer-by-layer accuracy table)

Usage:
    python exp1_linear_probe.py --subject qwen
    python exp1_linear_probe.py --subject llama --activations-dir outputs/activations_llama
"""

from __future__ import annotations

import argparse
import json
import pickle
from collections import defaultdict
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedShuffleSplit

from config import (
    ACTIVATIONS_DIR,
    LEAVE_ONE_DOMAIN_OUT,
    OUTPUTS_DIR,
    PROBE_C,
    PROBE_TRAIN_FRAC,
    PROBE_VAL_FRAC,
    PROBES_DIR,
    SEED,
)


def parse_act_filename(path: Path) -> dict:
    # filename pattern: <scenario_id>__<direction>__t<idx>__<condition>.npz
    stem = path.stem
    parts = stem.split("__")
    scenario_id, direction, trial = parts[0], parts[1], parts[2]
    condition = parts[3]
    trial_idx = int(trial.lstrip("t"))
    domain = scenario_id.split("_")[0] if "_" in scenario_id else scenario_id
    return {
        "scenario_id": scenario_id,
        "direction": direction,
        "trial_idx": trial_idx,
        "condition": condition,
        "domain": domain,
        "path": path,
    }


def load_activations(activations_dir: Path) -> tuple[np.ndarray, dict, list[dict]]:
    """Returns:
        X_by_layer: dict[int, np.ndarray of shape (N, hidden_dim)]
        meta: list of dicts (one per row) with scenario_id, domain, condition, etc.
        labels: np.ndarray of shape (N,) with 1=TOOL_DIRECT, 0=USER_IMPERATIVE
    """
    files = sorted(activations_dir.glob("*.npz"))
    if not files:
        raise FileNotFoundError(f"No activation files in {activations_dir}; run run_subject_local.py --capture first.")

    rows: list[dict] = []
    X_by_layer: dict[int, list[np.ndarray]] = defaultdict(list)
    labels: list[int] = []

    for f in files:
        info = parse_act_filename(f)
        if info["condition"] not in ("TOOL_DIRECT", "USER_IMPERATIVE"):
            continue
        npz = np.load(f)
        layers = sorted(int(k.split("_")[1]) for k in npz.files if k.startswith("layer_"))
        for L in layers:
            X_by_layer[L].append(npz[f"layer_{L}"])
        rows.append(info)
        labels.append(1 if info["condition"] == "TOOL_DIRECT" else 0)

    X_by_layer_np = {L: np.stack(v, axis=0) for L, v in X_by_layer.items()}
    y = np.asarray(labels, dtype=np.int32)
    return X_by_layer_np, rows, y


def train_probe(X: np.ndarray, y: np.ndarray, train_idx: np.ndarray, test_idx: np.ndarray) -> tuple[LogisticRegression, float]:
    clf = LogisticRegression(C=PROBE_C, max_iter=2000, random_state=SEED, n_jobs=-1)
    clf.fit(X[train_idx], y[train_idx])
    acc = clf.score(X[test_idx], y[test_idx])
    return clf, acc


def scenario_stratified_split(rows: list[dict], y: np.ndarray, train_frac: float, val_frac: float
                              ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Train/val/test split where scenarios are held out (not just replicates).

    Returns indices into rows.
    """
    rng = np.random.default_rng(SEED)
    scenarios = sorted({r["scenario_id"] for r in rows})
    rng.shuffle(scenarios)
    n_train = int(round(train_frac * len(scenarios)))
    n_val = int(round(val_frac * len(scenarios)))
    train_s = set(scenarios[:n_train])
    val_s = set(scenarios[n_train:n_train + n_val])
    test_s = set(scenarios[n_train + n_val:])
    idx_train = np.array([i for i, r in enumerate(rows) if r["scenario_id"] in train_s])
    idx_val = np.array([i for i, r in enumerate(rows) if r["scenario_id"] in val_s])
    idx_test = np.array([i for i, r in enumerate(rows) if r["scenario_id"] in test_s])
    return idx_train, idx_val, idx_test


def leave_one_domain_out(X: np.ndarray, y: np.ndarray, rows: list[dict]) -> dict[str, float]:
    domains = sorted({r["domain"] for r in rows})
    accs: dict[str, float] = {}
    for held_out in domains:
        train_idx = np.array([i for i, r in enumerate(rows) if r["domain"] != held_out])
        test_idx = np.array([i for i, r in enumerate(rows) if r["domain"] == held_out])
        if len(test_idx) < 2 or len(train_idx) < 10:
            continue
        clf = LogisticRegression(C=PROBE_C, max_iter=2000, random_state=SEED, n_jobs=-1)
        clf.fit(X[train_idx], y[train_idx])
        accs[held_out] = float(clf.score(X[test_idx], y[test_idx]))
    return accs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--subject", default="qwen", help="qwen, llama, or any tag (controls output filenames)")
    parser.add_argument("--activations-dir", default=None,
                        help="Override activations dir (default: outputs/activations_<subject>)")
    parser.add_argument("--n-bootstrap", type=int, default=1000,
                        help="Bootstrap resamples for layer-wise accuracy CIs")
    args = parser.parse_args()

    activations_dir = Path(args.activations_dir) if args.activations_dir else OUTPUTS_DIR / f"activations_{args.subject}"
    if not activations_dir.exists():
        # Fall back to default activations dir
        activations_dir = ACTIVATIONS_DIR
        print(f"[WARN] activations_{args.subject} dir not found, falling back to {ACTIVATIONS_DIR}")
    probes_subdir = OUTPUTS_DIR / f"probes_{args.subject}"
    probes_subdir.mkdir(parents=True, exist_ok=True)

    print(f"Loading activations from {activations_dir}...")
    X_by_layer, rows, y = load_activations(activations_dir)
    n_layers = len(X_by_layer)
    n_trials = len(rows)
    hidden_dim = next(iter(X_by_layer.values())).shape[1]
    print(f"Loaded {n_trials} trials x {n_layers} layers x {hidden_dim} hidden dim.")
    print(f"Class balance: {int(y.sum())} TOOL_DIRECT, {len(y) - int(y.sum())} USER_IMPERATIVE.")

    idx_train, idx_val, idx_test = scenario_stratified_split(rows, y, PROBE_TRAIN_FRAC, PROBE_VAL_FRAC)
    n_train_scenarios = len({rows[i]["scenario_id"] for i in idx_train})
    n_test_scenarios = len({rows[i]["scenario_id"] for i in idx_test})
    print(f"Scenario-stratified split: train={len(idx_train)} ({n_train_scenarios} scenarios), "
          f"val={len(idx_val)}, test={len(idx_test)} ({n_test_scenarios} scenarios).")

    results: dict = {
        "subject": args.subject,
        "activations_dir": str(activations_dir),
        "n_trials": n_trials,
        "n_layers": n_layers,
        "hidden_dim": hidden_dim,
        "scenario_split": {"n_train": int(len(idx_train)), "n_val": int(len(idx_val)), "n_test": int(len(idx_test))},
        "layer_accuracy": {},
        "leave_one_domain_out": {},
    }

    rng = np.random.default_rng(SEED)
    for L in sorted(X_by_layer.keys()):
        X = X_by_layer[L]
        clf, test_acc = train_probe(X, y, idx_train, idx_test)
        val_acc = clf.score(X[idx_val], y[idx_val]) if len(idx_val) > 0 else None
        train_acc = clf.score(X[idx_train], y[idx_train])

        # Bootstrap 95% CI on test accuracy
        boot_accs = []
        for _ in range(args.n_bootstrap):
            samp = rng.integers(0, len(idx_test), size=len(idx_test))
            test_idx_boot = idx_test[samp]
            boot_accs.append(clf.score(X[test_idx_boot], y[test_idx_boot]))
        ci_lo = float(np.percentile(boot_accs, 2.5))
        ci_hi = float(np.percentile(boot_accs, 97.5))

        results["layer_accuracy"][str(L)] = {
            "train_acc": float(train_acc),
            "val_acc": float(val_acc) if val_acc is not None else None,
            "test_acc": float(test_acc),
            "test_acc_95ci": [ci_lo, ci_hi],
            "n_features": int(X.shape[1]),
        }
        with (probes_subdir / f"probe_layer_{L:02d}.pkl").open("wb") as fh:
            pickle.dump({"clf": clf, "C": PROBE_C, "layer": L, "subject": args.subject}, fh)

    if LEAVE_ONE_DOMAIN_OUT:
        print("\nLeave-one-domain-out generalization (per layer):")
        for L in sorted(X_by_layer.keys()):
            lod = leave_one_domain_out(X_by_layer[L], y, rows)
            results["leave_one_domain_out"][str(L)] = lod
            if lod:
                mean_acc = float(np.mean(list(lod.values())))
                results["layer_accuracy"][str(L)]["lod_mean_acc"] = mean_acc

    layer_sorted = sorted(X_by_layer.keys())
    test_accs = [results["layer_accuracy"][str(L)]["test_acc"] for L in layer_sorted]
    best_layer = int(layer_sorted[int(np.argmax(test_accs))])
    results["best_layer"] = best_layer
    results["best_layer_test_acc"] = float(max(test_accs))
    results["best_layer_95ci"] = results["layer_accuracy"][str(best_layer)]["test_acc_95ci"]

    out_path = OUTPUTS_DIR / f"exp1_results_{args.subject}.json"
    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2)

    print(f"\nBest layer: {best_layer} with test accuracy {max(test_accs):.3f} (95% CI {results['best_layer_95ci']})")
    print(f"Wrote {out_path}")
    print("Layer-by-layer test accuracy:")
    for L in layer_sorted:
        a = results["layer_accuracy"][str(L)]
        marker = "  <-- best" if L == best_layer else ""
        lod_str = f" lod={a.get('lod_mean_acc', 0):.3f}" if "lod_mean_acc" in a else ""
        print(f"  layer {L:>3} train={a['train_acc']:.3f} test={a['test_acc']:.3f} CI={a['test_acc_95ci']}{lod_str}{marker}")


if __name__ == "__main__":
    main()
