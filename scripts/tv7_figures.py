"""
TV  Figures of the temporal-validity paper from the finished runs (no data needed).

    python scripts/tv7_figures.py --x1 results/transactions/tv1_20261030_x1 \
        --x2 results/transactions/tv2_20261030_x2 --k4 results/kan/tv4_20261031_005129,results/kan/tv4_20261031_014421 \
        --out results/tv_figures
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt   # noqa: E402
import numpy as np                # noqa: E402
import pandas as pd               # noqa: E402

BLUE, ORANGE, AQUA, INK, MUTED = "#2a78d6", "#eb6834", "#1baf7a", "#222222", "#8a8a85"
plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.edgecolor": MUTED, "axes.labelcolor": INK, "xtick.color": INK, "ytick.color": INK,
                     "axes.grid": True, "grid.color": "#e6e6e3", "grid.linewidth": 0.6, "axes.axisbelow": True,
                     "legend.frameon": False, "pdf.fonttype": 42})


def fig_x1(x1: Path, out: Path):
    d = pd.read_csv(x1 / "metrics.csv")
    d = d[(d.label == "wallet") & (d.model == "lgbm") & d.features.isin(["causal", "lifetime"])]
    order = ["P1_random_rows", "P1b_random_entity", "P2_temporal_rows", "P3_temporal_entity",
             "P5_temporal_rows_new_addresses"]
    names = ["P1\nrandom rows", "P1b\nrandom addr.", "P2\ntemporal rows", "P3\ntemp., 1st row",
             "P5\ntemp., new addr."]
    g = d.groupby(["protocol", "features"]).auprc.agg(["mean", "std"])
    x = np.arange(len(order))
    fig, ax = plt.subplots(figsize=(6.4, 2.8))
    for i, (f, c, lab) in enumerate((("causal", BLUE, "causal (transactions up to the row's step)"),
                                     ("lifetime", ORANGE, "Elliptic++ lifetime features"))):
        m = [g.loc[(p, f), "mean"] for p in order]
        s = [g.loc[(p, f), "std"] for p in order]
        ax.bar(x + (i - 0.5) * 0.36, m, 0.34, yerr=s, color=c, label=lab, ecolor=INK, capsize=2,
               edgecolor="white", linewidth=1)
        for xi, v in zip(x + (i - 0.5) * 0.36, m):
            ax.text(xi, v + 0.02, f"{v:.2f}", ha="center", va="bottom", fontsize=7, color=INK)
    ax.set_xticks(x, names)
    ax.set_ylabel("Test AP (LightGBM, 3 seeds)")
    ax.set_ylim(0, 1.12)
    ax.legend(loc="upper right", fontsize=7.5, ncol=1)
    fig.tight_layout()
    fig.savefig(out / "fig_x1_causal_vs_lifetime.pdf")
    plt.close(fig)


def fig_elliptic(x2: Path, out: Path):
    d = pd.read_csv(x2 / "rolling_long.csv")
    ap = d[(d.kind == "ap") & (d.window == "all") & (d.model == "lgbm")].groupby("step").ap.agg(["mean", "min", "max"])
    mon = d[d.kind == "monitor"].set_index("step").sort_index()
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(6.4, 4.0), sharex=True)
    a1.fill_between(ap.index, ap["min"], ap["max"], color=BLUE, alpha=0.18, linewidth=0)
    a1.plot(ap.index, ap["mean"], color=BLUE, lw=2, marker="o", ms=3.5, label="LightGBM, mean of 5 seeds (band: min-max)")
    a1.set_ylabel("Step AP")
    a1.set_ylim(0, 1.05)
    a1.legend(loc="lower left", fontsize=7.5)
    a2.plot(mon.index, 100 * mon.true_prior, color=INK, lw=2, marker="o", ms=3.5, label="true illicit share (labelled)")
    a2.plot(mon.index, 100 * mon.em_prior, color=ORANGE, lw=2, marker="s", ms=3.5, ls="--",
            label="EM estimate from calibrated scores")
    a2.set_ylabel("Illicit share, %")
    a2.set_xlabel("Elliptic time step (test steps of cut-offs 20, 25, 30, 35, 40)")
    a2.legend(loc="upper right", fontsize=7.5)
    for ax in (a1, a2):
        for c in (29.5, 34.5, 39.5, 44.5):
            ax.axvline(c, color=MUTED, lw=0.8, ls=":")
        ax.axvline(42.5, color="#e34948", lw=1)
    a1.text(42.6, 0.95, "dark-market\nshutdown", fontsize=7, color=INK, va="top")
    fig.tight_layout()
    fig.savefig(out / "fig_elliptic_rolling_monitor.pdf")
    plt.close(fig)


def fig_k4(k4: list[Path], out: Path):
    t = pd.concat([pd.read_csv(p / "thresholds.csv") for p in k4])
    t = t[(t.split == "t2025") & (t.window == "all") & (t.budget == 1) & (t.model != "rule")]
    g = t.groupby(["model", "strategy"]).alarms_per_day_quiet.mean().unstack()
    models = ["lgbm", "rf", "mlp", "kan", "logreg"]
    labels = ["LightGBM", "RF", "MLP", "KAN", "Logistic"]
    x = np.arange(len(models))
    fig, ax = plt.subplots(figsize=(6.4, 2.6))
    for i, (s, c, lab) in enumerate((("fixed_incident", BLUE, "fixed on 2024 incident days"),
                                     ("fixed_quiet", ORANGE, "fixed on 2024 quiet days"),
                                     ("topk", AQUA, "top-k per day"))):
        v = g.loc[models, s].to_numpy()
        ax.bar(x + (i - 1) * 0.27, v, 0.25, color=c, label=lab, edgecolor="white", linewidth=1)
        for xi, vi in zip(x + (i - 1) * 0.27, v):
            ax.text(xi, vi * 1.08, f"{vi:.1f}", ha="center", va="bottom", fontsize=6.5, color=INK)
    ax.axhline(1, color=INK, lw=1, ls="--")
    ax.text(-0.5, 0.85, "budget 1/day", fontsize=7, color=INK, ha="left", va="top")
    ax.set_yscale("log")
    ax.set_yticks([1, 3, 10, 30], ["1", "3", "10", "30"])
    ax.set_xlim(-0.55, len(models) - 0.45)
    ax.set_ylim(0.5, 80)
    ax.set_xticks(x, labels)
    ax.set_ylabel("Alarms per quiet day, 2025-26")
    ax.legend(loc="upper right", fontsize=7.5, ncol=3, bbox_to_anchor=(1, 1.18))
    fig.tight_layout()
    fig.savefig(out / "fig_k4_quiet_alarms.pdf")
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--x1", required=True)
    ap.add_argument("--x2", required=True)
    ap.add_argument("--k4", required=True)
    ap.add_argument("--out", default="results/tv_figures")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    fig_x1(Path(a.x1), out)
    fig_elliptic(Path(a.x2), out)
    fig_k4([Path(p) for p in a.k4.split(",")], out)
    print("wrote", out)


if __name__ == "__main__":
    main()
