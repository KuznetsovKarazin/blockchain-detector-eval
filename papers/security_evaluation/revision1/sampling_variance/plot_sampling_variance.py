"""Export fig05 from the completed frozen historical sampling diagnostic."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
MODES = ("other_files_unrestricted", "project_disjoint", "clone_disjoint", "joint_project_clone_disjoint")
METHODS = ("raw_tfidf_lr", "normalized_tfidf_lr", "pattern_rf", "pattern_lightgbm")
NAMES = ("Raw TF-IDF + logistic regression", "Normalized TF-IDF + logistic regression",
         "Pattern random forest (500 trees)", "Pattern LightGBM (400 estimators)")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=ROOT / "papers/security_evaluation/manuscript/figures_revision1")
    args = parser.parse_args()
    manifest = json.loads((args.run / "manifest.json").read_text())
    if manifest["status"] != "complete_conditional_diagnostic":
        raise ValueError("Use completed run only; no selective early plot")
    ranking_path = args.run / "summary/per_evaluation_ranking.csv"
    reference_path = args.run / "summary/random_ranking_reference.json"
    for path in (ranking_path, reference_path):
        if sha(path) != manifest["summary_hashes"][str(path.relative_to(args.run))]:
            raise ValueError("Summary artifact hash changed")
    frame = pd.read_csv(ranking_path)
    main = frame[frame.panel == "training_draw"]
    if len(main) != 320 or (main.status == "failed").any():
        raise ValueError("Expected complete main grid without failures; handle missingness explicitly before plotting")
    if not (main.estimator_seed == 0).all():
        raise ValueError("Main panel must fix estimator randomness")
    reference = json.loads(reference_path.read_text())
    baseline = reference["exact_ap_mean"]
    args.out.mkdir(parents=True, exist_ok=True)
    prefix = args.out / "fig05_sampling_variance"
    caption = (
        "Conditional variation in proxy-label average precision across 20 paired training draws, "
        "using the original fixed historical pilot test (1,082 files; 21 SWC-107 findings; one historical joint component). "
        "Every draw has 1,179 training files and 31 proxy positives. Estimator seed is fixed at zero for every method. "
        "Dots denote draw outcomes; boxes show the median and interquartile range and whiskers the observed minimum and maximum, "
        "not confidence intervals. The joint restriction uses the complete available pool, so its 20 logical draws share one "
        "unique training membership and reused fit, plotted as a single diamond. The dashed line is the exact expected AP "
        "of a uniformly random strict ranking, not prevalence or an inferential decision threshold. These distributions describe "
        "training-subset variation on a reused dependent test and do not measure uncertainty for unseen projects or families."
    )
    provenance = {"figure": prefix.name, "run_fingerprint": manifest["run_fingerprint"],
                  "source_hash": sha(__file__), "input_hashes": {str(p): sha(p) for p in (ranking_path, reference_path)},
                  "caption": caption, "exact_random_ranking_ap_mean": baseline,
                  "quantiles_are_confidence_intervals": False, "main_estimator_seed": 0,
                  "joint_unique_training_memberships": 1, "output_hashes": {}}
    # Provenance exists before rendering; plotting has no fit/model-selection step.
    provenance_path = args.out / "fig05_provenance.json"
    provenance_path.write_text(json.dumps(provenance, indent=2) + "\n")
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.titlesize": 11,
                         "axes.labelsize": 10, "svg.fonttype": "none", "pdf.fonttype": 42})
    fig, axes = plt.subplots(2, 2, figsize=(10, 7.0), sharey=True)
    colors = ("#146B8C", "#35754A", "#88589B", "#BD6A29")
    rng = np.random.default_rng(0)  # display jitter only; does not touch study draws
    ymax = max(float(main.ap_proxy.max()) * 1.12, baseline * 1.5)
    for ax, method, title, color in zip(axes.ravel(), METHODS, NAMES, colors):
        part = main[main.method == method]
        for index, regime in enumerate(MODES, 1):
            cell = part[part.regime == regime].sort_values("draw")
            if len(cell) != 20:
                raise ValueError("Missing training draw in plot")
            values = cell.ap_proxy.to_numpy()
            if regime == MODES[-1]:
                if cell.training_membership_sha256.nunique() != 1 or len(np.unique(values)) != 1:
                    raise ValueError("Joint control not identical")
                ax.scatter([index], [values[0]], marker="D", s=55, color=color, edgecolor="white", linewidth=.6, zorder=4)
            else:
                ax.boxplot([values], positions=[index], widths=.44, whis=(0, 100), showfliers=False,
                           patch_artist=True, boxprops={"facecolor": color, "alpha": .14, "edgecolor": color},
                           medianprops={"color": color, "linewidth": 1.5},
                           whiskerprops={"color": color, "linewidth": .9}, capprops={"color": color, "linewidth": .9})
                ax.scatter(index + rng.uniform(-.14, .14, len(values)), values, s=20,
                           color=color, alpha=.7, edgecolor="white", linewidth=.3, zorder=3)
        ax.axhline(baseline, color="#515151", linestyle=(0, (4, 3)), linewidth=1, zorder=1)
        ax.set_title(title, loc="left", pad=9)
        ax.set_xticks(range(1, 5), ["Unrestricted", "Project", "Clone", "Joint\n(one unique set)"])
        ax.set_ylim(0, ymax)
        ax.set_xlim(.5, 4.5)
        ax.grid(axis="y", color="#E2E5E8", linewidth=.6, zorder=0)
        ax.spines[["top", "right"]].set_visible(False)
        ax.set_axisbelow(True)
    axes[0, 0].set_ylabel("Proxy-label average precision")
    axes[1, 0].set_ylabel("Proxy-label average precision")
    fig.suptitle("Training-subset variation on the fixed historical pilot", x=.08, ha="left", fontsize=14, y=.985)
    fig.text(.08, .928, f"20 paired draws · 1,179 training files / 31 findings · fixed estimator seed 0", fontsize=10, color="#454B50")
    fig.text(.08, .035, f"Dashed line: exact random-ranking mean AP = {baseline:.5f}. Ranges are descriptive, not confidence intervals.", fontsize=9)
    fig.subplots_adjust(left=.08, right=.985, bottom=.12, top=.86, hspace=.39, wspace=.15)
    for suffix in ("png", "pdf", "svg"):
        path = prefix.with_suffix("." + suffix)
        fig.savefig(path, dpi=220, bbox_inches="tight", facecolor="white")
        provenance["output_hashes"][path.name] = sha(path)
    plt.close(fig)
    provenance_path.write_text(json.dumps(provenance, indent=2) + "\n")
    print(json.dumps({"figure": str(prefix), "run_fingerprint": manifest["run_fingerprint"]}))


if __name__ == "__main__":
    main()
