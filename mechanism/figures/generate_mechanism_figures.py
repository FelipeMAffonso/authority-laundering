"""Generate cross-subject mechanism figures for the Mechanism section of the paper.

Reads exp1_results_<subject>.json (probing accuracy by layer), exp2_results_<subject>.json
(probe-compliance correlation), and optionally exp3_results_<subject>.json (causal patching)
for the three open-weight subjects (llama, mistral, qwen).

Writes:
  - paper/figures/fig8_probing.png            (cross-subject probing accuracy by layer)
  - paper/figures/fig9_compliance_correlation.png  (cross-subject probe-compliance AUC)
  - paper/figures/fig10_patching.png          (causal patching, only if exp3 has data)

Style: ochre (#D9A441), neutral grey (#7F8C8D), thin spines, no gridlines.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

MECH_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = MECH_DIR.parent
PAPER_FIG_DIR = PROJECT_ROOT / "paper" / "figures"
PAPER_FIG_DIR.mkdir(parents=True, exist_ok=True)

OCHRE = "#D9A441"
GREY = "#7F8C8D"
DARK = "#1F2937"
GREEN = "#2E7D4E"
RED = "#C0392B"
BLUE = "#2C6E91"

# Four subjects with display labels and colors. Listed in ascending behavioural
# channel-asymmetry order (Qwen flat -> Llama 3.1 8B strongly asymmetric) so
# that fig9 reads left-to-right as a tracking story.
PURPLE = "#7B4FA0"
SUBJECTS = [
    ("qwen", "Qwen 2.5 7B", GREEN),
    ("mistral", "Mistral 7B v0.3", BLUE),
    ("llama32_3b", "Llama 3.2 3B", PURPLE),
    ("llama", "Llama 3.1 8B", OCHRE),
]

# Behavioural channel-asymmetry (TOOL minus USER, percentage points) per subject,
# from the paper's open-weight panel.
BEHAVIOURAL_GAP_PP = {
    "qwen": 2.7,
    "mistral": 12.0,
    "llama32_3b": 18.6,
    "llama": 54.2,
}

# Theory-derived horizontal reference lines.
THEOREM3_FLOOR = 0.545
THEOREM4_LOW = 0.579
THEOREM4_HIGH = 0.659

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 11,
    "axes.labelsize": 12,
    "axes.titlesize": 12,
    "xtick.labelsize": 11,
    "ytick.labelsize": 11,
    "legend.fontsize": 10,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.linewidth": 0.6,
    "xtick.major.width": 0.6,
    "ytick.major.width": 0.6,
})


def _load_json(path: Path):
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def fig8_probing() -> None:
    """Cross-subject probing accuracy by layer overlay."""
    fig, ax = plt.subplots(figsize=(6.6, 3.8))

    plotted_any = False
    for subject, label, color in SUBJECTS:
        path = MECH_DIR / "outputs" / f"exp1_results_{subject}.json"
        data = _load_json(path)
        if data is None:
            print(f"Skipping {subject} in Fig 8: {path} not found.")
            continue
        layer_acc = data["layer_accuracy"]
        layers = sorted(int(L) for L in layer_acc.keys())
        test_acc = [layer_acc[str(L)]["test_acc"] for L in layers]
        ax.plot(layers, test_acc, color=color, linewidth=1.6, marker="o",
                markersize=3.2, label=label)
        # Annotate best layer.
        best_layer = data.get("best_layer")
        best_acc = data.get("best_layer_test_acc")
        if best_layer is not None and best_acc is not None:
            ax.annotate(
                f"L{best_layer}",
                xy=(best_layer, best_acc),
                xytext=(best_layer, min(1.02, best_acc + 0.03)),
                ha="center", va="bottom",
                fontsize=10, color=color,
            )
        plotted_any = True

    if not plotted_any:
        print("No exp1_results_<subject>.json files found; skipping Fig 8.")
        plt.close(fig)
        return

    # Theory floor (Theorem 3) and Gaussian-sharpened band (Theorem 4).
    ax.axhline(THEOREM3_FLOOR, color=DARK, linewidth=0.7, linestyle="--",
               label="Theorem 3 floor")
    ax.axhspan(THEOREM4_LOW, THEOREM4_HIGH, color=GREY, alpha=0.18,
               label="Theorem 4 range")
    ax.axhline(0.5, color=GREY, linewidth=0.5, linestyle=":")

    ax.set_xlabel("Layer")
    ax.set_ylabel("Probe test accuracy")
    ax.set_ylim(0.4, 1.04)
    # Legend outside the plot area on the right-hand side.
    ax.legend(loc="center left", bbox_to_anchor=(1.02, 0.5),
              frameon=False, fontsize=10, ncol=1)

    plt.tight_layout()
    out = PAPER_FIG_DIR / "fig8_probing.png"
    fig.savefig(out, dpi=300, bbox_inches="tight")
    fig.savefig(out.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote {out}")


def fig9_compliance_correlation() -> None:
    """Probe-compliance AUC plotted against the behavioural channel-asymmetry
    of each subject. Two panels: (a) scatter of pooled AUC vs behavioural gap,
    showing the tracking relationship; (b) within-channel AUC (TOOL only and
    USER only) per subject, showing the probe predicts compliance only when
    compliance varies with channel."""
    fig, (ax_a, ax_b) = plt.subplots(1, 2, figsize=(7.8, 3.8),
                                     gridspec_kw={"width_ratios": [1.0, 1.3]})

    # Panel a: scatter of pooled AUC vs behavioural channel-asymmetry.
    # Per-subject label placement so the two low-asymmetry points (Qwen,
    # Mistral) do not overlap each other or their markers.
    LABEL_OFFSET = {
        "qwen": (8, -14), "mistral": (8, 8),
        "llama32_3b": (8, 4), "llama": (-10, 7),
    }
    LABEL_HA = {"llama": "right"}
    plotted_any = False
    xs, ys = [], []
    for subject, label, color in SUBJECTS:
        path = MECH_DIR / "outputs" / f"exp2_results_{subject}.json"
        data = _load_json(path)
        if data is None:
            print(f"Skipping {subject} in Fig 9: {path} not found.")
            continue
        pooled = (data.get("pooled") or {}).get("auc")
        gap = BEHAVIOURAL_GAP_PP.get(subject)
        if pooled is None or gap is None:
            continue
        ax_a.scatter([gap], [pooled], s=70, color=color, edgecolor=DARK,
                     linewidth=0.7, zorder=3, label=label)
        ax_a.annotate(label, xy=(gap, pooled),
                      xytext=LABEL_OFFSET.get(subject, (6, 4)),
                      textcoords="offset points",
                      ha=LABEL_HA.get(subject, "left"),
                      fontsize=10, color=DARK)
        xs.append(gap)
        ys.append(pooled)
        plotted_any = True

    if not plotted_any:
        print("No exp2_results_<subject>.json files found; skipping Fig 9.")
        plt.close(fig)
        return

    # Best-fit line across the four subjects.
    if len(xs) >= 2:
        xs_arr, ys_arr = np.array(xs), np.array(ys)
        slope, intercept = np.polyfit(xs_arr, ys_arr, 1)
        x_line = np.linspace(0, max(xs_arr) * 1.05, 50)
        ax_a.plot(x_line, slope * x_line + intercept,
                  color=GREY, linewidth=0.8, linestyle="--", zorder=1)
        # Pearson r for annotation.
        r = float(np.corrcoef(xs_arr, ys_arr)[0, 1])
        ax_a.text(0.97, 0.05, f"r = {r:.2f}", transform=ax_a.transAxes,
                  ha="right", va="bottom", fontsize=10, color=DARK)

    ax_a.axhline(0.5, color=DARK, linewidth=0.6, linestyle=":")
    ax_a.set_xlabel("TOOL – USER gap (pp)")
    ax_a.set_ylabel("Pooled probe-compliance AUC")
    ax_a.set_ylim(0.4, 1.0)
    ax_a.set_xlim(-4, max(xs) * 1.15 if xs else 60)
    ax_a.text(0.02, 0.97, "a", transform=ax_a.transAxes, fontsize=13,
              fontweight="bold", va="top")

    # Panel b: within-channel AUC bars per subject.
    n_subjects = len(SUBJECTS)
    width = 0.36
    x_positions = np.arange(n_subjects)
    tool_aucs, user_aucs = [], []
    subject_labels = []
    for subject, label, _ in SUBJECTS:
        path = MECH_DIR / "outputs" / f"exp2_results_{subject}.json"
        data = _load_json(path)
        if data is None:
            tool_aucs.append(np.nan)
            user_aucs.append(np.nan)
            subject_labels.append(label)
            continue
        tool_aucs.append((data.get("tool_direct_only") or {}).get("auc", np.nan))
        user_aucs.append((data.get("user_imperative_only") or {}).get("auc", np.nan))
        subject_labels.append(label)

    bars_t = ax_b.bar(x_positions - width / 2, tool_aucs, width=width,
                      color=BLUE, edgecolor=DARK, linewidth=0.5,
                      label="Within TOOL_DIRECT")
    bars_u = ax_b.bar(x_positions + width / 2, user_aucs, width=width,
                      color=OCHRE, edgecolor=DARK, linewidth=0.5,
                      label="Within USER_IMPERATIVE")
    # Value labels with a per-group vertical stagger so near-equal TOOL/USER bars
    # (e.g. Qwen 0.47/0.51) do not collide.
    for i in range(n_subjects):
        t, u = tool_aucs[i], user_aucs[i]
        bump_t = bump_u = 0.015
        if not (np.isnan(t) or np.isnan(u)) and abs(t - u) < 0.06:
            if u >= t:
                bump_u = 0.055
            else:
                bump_t = 0.055
        if not np.isnan(t):
            ax_b.text(x_positions[i] - width / 2, t + bump_t, f"{t:.2f}",
                      ha="center", va="bottom", fontsize=10, color=DARK)
        if not np.isnan(u):
            ax_b.text(x_positions[i] + width / 2, u + bump_u, f"{u:.2f}",
                      ha="center", va="bottom", fontsize=10, color=DARK)

    ax_b.axhline(0.5, color=DARK, linewidth=0.7, linestyle="--",
                 label="Chance (AUC = 0.5)")
    ax_b.set_xticks(x_positions)
    ax_b.set_xticklabels(subject_labels, rotation=20, ha="right", fontsize=10)
    ax_b.set_ylabel("Within-channel AUC")
    ax_b.set_ylim(0.0, 1.05)
    ax_b.text(0.02, 0.97, "b", transform=ax_b.transAxes, fontsize=13,
              fontweight="bold", va="top")
    # Legend outside the plot area on the right.
    ax_b.legend(loc="center left", bbox_to_anchor=(1.02, 0.5),
                frameon=False, fontsize=10)

    plt.tight_layout()
    out = PAPER_FIG_DIR / "fig9_compliance_correlation.png"
    fig.savefig(out, dpi=300, bbox_inches="tight")
    fig.savefig(out.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote {out}")


def fig10_patching() -> None:
    """Cross-subject causal patching flip rates (only if mcnemar p is non-null)."""
    fig, ax = plt.subplots(figsize=(7.0, 3.6))

    bar_specs = [
        ("tool_to_user", "Patch tool->user\n(compliance->refusal)", GREEN),
        ("user_to_tool", "Patch user->tool\n(refusal->compliance)", RED),
    ]
    n_bars = len(bar_specs)
    n_subjects = len(SUBJECTS)
    width = 0.24
    x_positions = np.arange(n_bars)

    plotted_any = False
    annotations = []
    for idx, (subject, label, color) in enumerate(SUBJECTS):
        path = MECH_DIR / "outputs" / f"exp3_results_{subject}.json"
        data = _load_json(path)
        if data is None:
            continue
        if data.get("mcnemar_two_sided_p") is None:
            print(f"Skipping {subject} in Fig 10: mcnemar_two_sided_p is null.")
            continue
        directions = data.get("directions", {})
        rates = []
        ns = []
        for direction_key, _, _ in bar_specs:
            info = directions.get(direction_key, {}) or {}
            rates.append(info.get("flip_rate"))
            ns.append(info.get("n_done", 0))
        offset = (idx - (n_subjects - 1) / 2) * width
        bars = ax.bar(x_positions + offset,
                      [r if r is not None else 0 for r in rates],
                      width=width, color=color, edgecolor=DARK, linewidth=0.5,
                      label=label)
        for bar, r, n in zip(bars, rates, ns):
            if r is None:
                continue
            ax.text(bar.get_x() + bar.get_width() / 2, r + 0.02,
                    f"{r:.0%}\nN={n}", ha="center", va="bottom", fontsize=7.0)
        annotations.append(f"{label}: McNemar p = {data['mcnemar_two_sided_p']:.3g}")
        plotted_any = True

    if not plotted_any:
        print("No exp3_results_<subject>.json with non-null McNemar p found; skipping Fig 10.")
        plt.close(fig)
        return

    ax.set_xticks(x_positions)
    ax.set_xticklabels([label for _, label, _ in bar_specs])
    ax.set_ylabel("Compliance flip rate")
    ax.legend(loc="upper right", frameon=False, fontsize=7.5)
    if annotations:
        ax.set_title("\n".join(annotations), loc="left", fontsize=8, pad=6)

    plt.tight_layout()
    out = PAPER_FIG_DIR / "fig10_patching.png"
    fig.savefig(out, dpi=300, bbox_inches="tight")
    fig.savefig(out.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote {out}")


if __name__ == "__main__":
    fig8_probing()
    fig9_compliance_correlation()
    fig10_patching()
