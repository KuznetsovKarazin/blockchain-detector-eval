"""Verify and report a completed diagnostic; never fits or selects models."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "papers/security_evaluation"))
from campaign import run_development as campaign

NAMES = {"other_files_unrestricted": "Unrestricted", "project_disjoint": "Project",
         "clone_disjoint": "Clone", "joint_project_clone_disjoint": "Joint"}
METHODS = {"raw_tfidf_lr": "Raw TF-IDF LR", "normalized_tfidf_lr": "Normalized TF-IDF LR",
           "pattern_rf": "Pattern RF500", "pattern_lightgbm": "Pattern LightGBM400"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, type=Path)
    args = parser.parse_args()
    run = args.run
    manifest = json.loads((run / "manifest.json").read_text())
    if manifest["status"] != "complete_conditional_diagnostic":
        raise ValueError("Completed grid required")
    campaign.verify_hashes(ROOT, manifest["source_hashes"])
    campaign.verify_hashes(run / "code_snapshot", manifest["source_hashes"])
    campaign.verify_hashes(ROOT, manifest["input_hashes"])
    campaign.verify_hashes(run, manifest["summary_hashes"])
    config = json.loads((run / "config.json").read_text())
    if campaign.sha(run / "config.json") != manifest["config_sha256"]:
        raise ValueError("Changed config")
    historical = pd.read_csv(ROOT / campaign.HISTORICAL_PILOT / "predictions.csv", float_precision="round_trip")
    reproduction, result_hashes, counts = [], {}, {"logical": 0, "physical": 0, "failed": 0, "convergence_warnings_physical": 0}
    peak, physical_seconds = 0.0, 0.0
    for job in config["jobs"]:
        path = run / "fits" / job["job_id"] / "result.json"
        result = campaign.checked_result(path, manifest["run_fingerprint"])
        counts["logical"] += 1
        counts["physical"] += result["physical_fit"]
        counts["failed"] += result["status"] == "failed"
        result_hashes[str(path.relative_to(run))] = campaign.sha(path)
        resource = json.loads((path.parent / result["resources_path"]).read_text())
        if result["physical_fit"]:
            physical_seconds += resource.get("total_seconds", 0)
            counts["convergence_warnings_physical"] += bool(resource.get("convergence_warning"))
        peak = max(peak, resource.get("process_peak_rss_mib_cumulative", 0))
        if job["panel"] == "training_draw" and job["draw"] == 0 and job["method"] == "raw_tfidf_lr":
            prior = historical[historical.regime == job["regime"]].sort_values("file_id")
            new = pd.read_csv(path.parent / result["predictions_path"], float_precision="round_trip")
            if new.file_id.tolist() != prior.file_id.tolist():
                raise ValueError("Reproduction test identities differ")
            difference = float(np.max(np.abs(new.score.to_numpy() - prior.score.to_numpy())))
            reproduction.append({"regime": job["regime"], "max_absolute_score_difference": difference,
                                 "scores_bitwise_equal_after_roundtrip_parse": bool(np.array_equal(new.score, prior.score))})
    if counts["logical"] != 360 or counts["physical"] != 282:
        raise ValueError("Incomplete unexpected fit count")
    summary = run / "summary"
    distribution = pd.read_csv(summary / "conditional_distributions.csv")
    ap = distribution[distribution.metric == "ap_proxy"]
    paired = pd.read_csv(summary / "paired_difference_distributions.csv")
    ref = json.loads((summary / "random_ranking_reference.json").read_text())
    lines = ["# Conditional historical-pilot training variation", "",
             "This completed post-pilot diagnostic uses the exact original T: 1,082 files, 21 proxy positives, one historical joint component. "
             "It measures variation from training-subset selection on this fixed dependent test, not uncertainty for new projects or families. "
             "The external and expanded-graph comparative gates remain unchanged and blocked.", "",
             f"Run fingerprint: `{manifest['run_fingerprint']}`.", "",
             f"All {counts['logical']} logical evaluations completed ({counts['physical']} physical fits; {counts['failed']} failures; "
             f"{counts['convergence_warnings_physical']} physical fits with convergence warnings). "
             f"Physical-fit preprocessing/fit/prediction total: {physical_seconds / 60:.2f} minutes. Cumulative process peak RSS: {peak:.2f} MiB.", "",
             "The main panel fixes estimator seed zero and uses 20 paired training draws per regime/method, each with 1,179 files and 31 proxy positives. "
             "The joint pool has only one unique training membership; all its main-panel repeats reuse the same fit. "
             "All four raw-LR draw-zero score vectors exactly reproduce the original pilot." if all(x["scores_bitwise_equal_after_roundtrip_parse"] for x in reproduction) else "Reproduction differences are recorded in POST_RUN_READINESS.json.",
             "", "## Main-panel AP distributions", "",
             "Quantiles and ranges below describe the 20 training draws. They are not confidence intervals.", "",
             "| Method | Regime | Unique training sets | Mean AP | SD | 2.5% quantile | Median | 97.5% quantile | Min–max |",
             "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    for method, name in METHODS.items():
        for regime, display in NAMES.items():
            r = ap[(ap.panel == "training_draw") & (ap.method == method) & (ap.regime == regime)].iloc[0]
            lines.append(f"| {name} | {display} | {int(r.n_distinct_training_memberships)} | {r['mean']:.6f} | {r.sd:.6f} | {r.q025:.6f} | {r['median']:.6f} | {r.q975:.6f} | {r['min']:.6f}–{r['max']:.6f} |")
    lines += ["", "## Paired AP differences relative to joint", "",
              "Each difference uses the same draw index, fixed estimator seed and fixed T. The positive fraction is a descriptive count over draws, not a p-value.", "",
              "| Method | Contrast | Mean difference | 2.5% quantile | Median | 97.5% quantile | Positive draws |",
              "|---|---|---:|---:|---:|---:|---:|"]
    relevant = paired[(paired.metric == "ap_proxy") & (paired.right_regime == "joint_project_clone_disjoint")]
    for method, name in METHODS.items():
        for regime, display in list(NAMES.items())[:-1]:
            r = relevant[(relevant.method == method) & (relevant.left_regime == regime)].iloc[0]
            lines.append(f"| {name} | {display} − joint | {r['mean']:.6f} | {r.q025:.6f} | {r['median']:.6f} | {r.q975:.6f} | {round(r.fraction_positive_descriptive * 20):d}/20 |")
    lines += ["", "## Estimator-seed panel on the fixed joint pool", "",
              "This panel changes only the tree estimator seed (0–19); training membership is identical. It is separate from training-selection variation.", "",
              "| Method | Mean AP | SD | Minimum | Maximum |", "|---|---:|---:|---:|---:|"]
    for _, r in ap[ap.panel == "joint_estimator_seed"].iterrows():
        lines.append(f"| {METHODS[r.method]} | {r['mean']:.6f} | {r.sd:.6f} | {r['min']:.6f} | {r['max']:.6f} |")
    lines += ["", "## Uniform random-ranking reference", "",
              f"The exact expected AP is **{ref['exact_ap_mean']:.12f}**, compared with proxy prevalence **{ref['prevalence_proxy']:.12f}**. "
              f"For the frozen 10,000 random rankings, mean AP is {ref['ap_summary']['mean']:.6f}, median {ref['ap_summary']['median']:.6f}, "
              f"and descriptive 2.5%/97.5% quantiles {ref['ap_summary']['q025']:.6f}/{ref['ap_summary']['q975']:.6f}. "
              "These are a stipulated strict random-ordering reference, not an inferential permutation test or a fitted method. No p-values are computed.", "",
              "Workload budgets are exactly 54, 108 and 216 reviews. Full per-draw workload, coverage, boundary-tie expectations/ranges and all six paired regime differences are in `summary/`. "
              "The original frozen reference helper was validated for these budgets; its generic floating-point budget calculation can underflow at unrelated fractions such as 0.29×100. "
              "That edge case does not affect this run and is handled in a separately versioned generic utility without changing the executed source.", "",
              "`run_20261025_v1` is a preserved unused preflight, never scored. The executed experiment is `run_20261025_v2`. "
              "Proxy-label agreement, conditional historical dependence and the previously exposed test remain limitations; none of these results certifies expanded-graph independence or external detection quality.", ""]
    report = run / "RESULTS.md"
    report.write_text("\n".join(lines))
    readiness = {"schema": "historical_sampling_postrun_review_v1", "run_fingerprint": manifest["run_fingerprint"],
                 "analysis_source_sha256": campaign.sha(__file__), "counts": counts,
                 "physical_preprocessing_fit_predict_seconds": physical_seconds,
                 "cumulative_process_peak_rss_mib": peak, "raw_lr_original_reproduction": reproduction,
                 "all_result_manifests_hash": campaign.fingerprint(result_hashes),
                 "fixed_actual_review_budgets": [54, 108, 216],
                 "external_scores_computed": False, "independence_claim": False,
                 "inferential_p_values_or_new_family_CI": False, "report_sha256": campaign.sha(report),
                 "summary_hashes_verified": manifest["summary_hashes"]}
    campaign.dump(run / "POST_RUN_READINESS.json", readiness)
    print(json.dumps({"counts": counts, "report": str(report), "peak_MiB": peak}))


if __name__ == "__main__":
    main()
