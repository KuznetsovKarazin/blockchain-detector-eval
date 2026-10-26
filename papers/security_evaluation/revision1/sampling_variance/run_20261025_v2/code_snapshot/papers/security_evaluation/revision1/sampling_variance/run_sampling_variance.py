"""Conditional historical-pilot training variation; no new independence claim.

Separate prepare/run stages freeze sources, original T, and all training draws.
This is an explicitly authorized diagnostic, not an override of the comparative
campaign gate. Only the original already-scored historical pilot T is accepted.
"""
from __future__ import annotations

import argparse
import gc
import importlib.util
import itertools
import json
import os
from pathlib import Path
import shutil
import sys
import time

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "papers/security_evaluation")]
from campaign import run_development as campaign
_spec = importlib.util.spec_from_file_location("historical_fixed_t", ROOT / "papers/security_evaluation/code/fixed_t_development.py")
fixed = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fixed)

HERE = "papers/security_evaluation/revision1/sampling_variance"
PILOT = campaign.HISTORICAL_PILOT
REGIMES = campaign.REGIMES
METHODS = campaign.METHODS
PURPOSE = "conditional_historical_pilot_training_variation_only"
MEMBERSHIP_SHA = "9f6281fa2343c997f3771e76e1d76ec4e84f94889e60ae6ee99e7fc52f6c1e1d"
INVENTORY_SHA = "26d23cc683ebfd9cd983d6348e98a048a26c5bcff21b27a2797938c6c30e26da"
GATE = "papers/security_evaluation/design_feasibility/expanded_sensitivity_recovered_20261025_v1/CAMPAIGN_GATE.json"
CODE = (f"{HERE}/run_sampling_variance.py", f"{HERE}/random_ranking_reference.py",
        f"{HERE}/test_sampling_variance.py", "tests/test_security_random_ranking_reference.py",
        f"{HERE}/PROTOCOL.md", "papers/security_evaluation/campaign/run_development.py",
        "papers/security_evaluation/code/fixed_t_development.py",
        "papers/security_evaluation/evaluation_metrics.py", "src/bal/data/contracts.py",
        "src/bal/features/contract_features.py")
sha, dump, fingerprint = campaign.sha, campaign.dump, campaign.fingerprint


def original_inputs():
    pilot = ROOT / PILOT
    expected = {"memberships.csv": MEMBERSHIP_SHA, "source_inventory.csv": INVENTORY_SHA,
                "predictions.csv": campaign.HISTORICAL_PREDICTIONS_SHA256}
    campaign.verify_hashes(pilot, expected)
    manifest = json.loads((pilot / "manifest.json").read_text())
    if manifest["status"] != "complete_development_only" or manifest["test_n"] != 1082:
        raise ValueError("Only original completed historical pilot is authorized")
    campaign.verify_hashes(pilot, {"label_input_hashes.json": manifest["label_inputs_sha256"]})
    campaign.verify_hashes(ROOT, manifest["input_files"])
    inventory = pd.read_csv(pilot / "source_inventory.csv")
    campaign.verify_inventory(inventory)
    pop = inventory[inventory.dataset == "dappscan"].copy()
    dapp = ROOT / "data/raw/DAppSCAN"
    if campaign.git("rev-parse", "HEAD", cwd=dapp) != campaign.DAPP_PIN:
        raise ValueError("DAppSCAN commit changed")
    if campaign.git("status", "--porcelain", "--untracked-files=no", cwd=dapp):
        raise ValueError("DAppSCAN tracked files changed")
    for row in pop.itertuples():
        if sha(campaign.source_path(row.path)) != row.file_sha256:
            raise ValueError(f"Source changed: {row.path}")
    label_hashes = json.loads((pilot / "label_input_hashes.json").read_text())
    labels, used = campaign.proxy_labels(pop, label_hashes)
    pop["reentrancy"] = [labels[i]["reentrancy"] for i in pop.file_id]
    members = pd.read_csv(pilot / "memberships.csv")
    test_ids = sorted(members.loc[members.role == "test", "file_id"].tolist())
    test = pop[pop.file_id.isin(test_ids)].sort_values("file_id")
    if len(pop) != 6587 or len(test) != 1082 or int(test.reentrancy.sum()) != 21 or test.joint_id.nunique() != 1:
        raise ValueError("Historical pilot population/counts changed")
    pools = fixed.training_pools(pop, test)
    matched, counts = fixed.matched_training(pools, "reentrancy", 0)
    if counts != {0: 1148, 1: 31}:
        raise ValueError("Historical matched counts changed")
    for regime, train in matched.items():
        old = sorted(members.loc[(members.role == "train") & (members.regime == regime), "file_id"].tolist())
        if train.file_id.tolist() != old:
            raise ValueError("Draw zero does not reproduce original training membership")
    gate = json.loads((ROOT / GATE).read_text())
    if gate.get("comparative_training_allowed") is not False:
        raise ValueError("Diagnostic cannot alter/reinterpret the blocked comparative gate")
    return pop, test, pools, labels, used


def make_jobs(pools, test):
    """Paired SHA ranks, fixed estimator seed; separate fixed-pool tree panel."""
    jobs, canonical = [], {}
    test_ids = test.file_id.tolist()
    def add(regime, train_ids, method, draw, estimator_seed, panel):
        identity = {"panel": panel, "draw": draw, "estimator_seed": estimator_seed,
                    "regime": regime, "method": method}
        reuse_key = fingerprint({"train_ids": train_ids, "test_ids": test_ids,
                                 "method": method, "estimator_seed": estimator_seed})
        job = {**identity, "job_id": fingerprint(identity)[:24],
               "test_id": "original_historical_pilot_T1082", "class": "reentrancy",
               "seed": estimator_seed, "train_ids": train_ids, "test_ids": test_ids,
               "training_membership_sha256": fingerprint(train_ids), "test_joint_components": 1,
               "reuse_from": canonical.get(reuse_key)}
        if reuse_key not in canonical:
            canonical[reuse_key] = job["job_id"]
        jobs.append(job)
    for draw in range(20):
        selected, counts = fixed.matched_training(pools, "reentrancy", draw)
        if counts != {0: 1148, 1: 31}:
            raise ValueError("Unmatched class counts")
        for regime in REGIMES:
            for method in METHODS:
                add(regime, selected[regime].file_id.tolist(), method, draw, 0, "training_draw")
    joint_ids = pools[REGIMES[-1]].sort_values("file_id").file_id.tolist()
    for seed in range(20):
        for method in METHODS[2:]:
            add(REGIMES[-1], joint_ids, method, None, seed, "joint_estimator_seed")
    return jobs


def validate_config(config, expected_jobs):
    """Narrow scope is checked independently of the self-consistent file hashes."""
    if config.get("purpose") != PURPOSE or config.get("external_scoring_allowed") is not False:
        raise ValueError("Wrong diagnostic purpose or external permission")
    if config.get("comparative_campaign_gate_override") is not False or config.get("independence_claim") is not False:
        raise ValueError("No comparative gate override or independence claim is authorized")
    if config.get("model_config") != campaign.model_config() or config.get("jobs") != expected_jobs:
        raise ValueError("Changed method parameters, original T, draw, regime, or seed panel")
    if config.get("review_fractions") != [.05, .1, .2] or config.get("n_draws") != 20:
        raise ValueError("Changed diagnostic metrics or draw count")
    if config.get("null_reference") != {"permutations": 10000, "seed": 20261025,
                                         "interpretation": "descriptive_not_inferential"}:
        raise ValueError("Changed random-ranking reference")


def prepare(out):
    if out.exists():
        raise FileExistsError(f"Refusing overwrite: {out}")
    pop, test, pools, labels, used = original_inputs()
    jobs = make_jobs(pools, test)
    config = {"schema": "historical_pilot_sampling_variance_v1", "purpose": PURPOSE,
              "created_utc": campaign.utc(), "external_scoring_allowed": False,
              "comparative_campaign_gate_override": False, "independence_claim": False,
              "proxy_class": "reentrancy", "n_draws": 20,
              "sampling": "original SHA256 path salt, paired class-stratified ranks, draw seeds 0..19",
              "estimator_randomness": "main estimator seed0; separate joint tree seeds0..19",
              "label_semantics": "SWC107 published finding vs no finding; proxy, not verified negatives",
              "model_config": campaign.model_config(), "review_fractions": [.05, .1, .2],
              "null_reference": {"permutations": 10000, "seed": 20261025,
                                 "interpretation": "descriptive_not_inferential"},
              "jobs": jobs, "tuning_budget": 0, "stopping_rule": "all frozen jobs; failures retained",
              "test_uncertainty": "fixed original one-component T; no new-family CI or inferential permutation p-value"}
    validate_config(config, jobs)
    out.mkdir(parents=True)
    dump(out / "config.json", config)
    dump(out / "environment.json", campaign.environment())
    dump(out / "annotation_hashes.json", used)
    snapshots = {}
    for relative in CODE:
        target = out / "code_snapshot" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
        snapshots[relative] = sha(target)
    inputs = {f"{PILOT}/{p}": sha(ROOT / PILOT / p) for p in
              ("manifest.json", "memberships.csv", "source_inventory.csv", "label_input_hashes.json", "predictions.csv")}
    inputs.update({campaign.HISTORY: sha(ROOT / campaign.HISTORY), GATE: sha(ROOT / GATE)})
    membership_rows = []
    for job in jobs:
        if job["panel"] == "training_draw" and job["method"] == METHODS[0]:
            membership_rows.extend({"draw": job["draw"], "regime": job["regime"], "role": "train", "file_id": i}
                                   for i in job["train_ids"])
    membership_rows.extend({"draw": -1, "regime": "common_test", "role": "test", "file_id": i}
                           for i in test.file_id)
    pd.DataFrame(membership_rows).to_csv(out / "memberships.csv.gz", index=False,
                                        compression={"method": "gzip", "mtime": 0})
    frozen = {"config_sha256": sha(out / "config.json"), "input_hashes": inputs,
              "source_hashes": snapshots, "environment_sha256": sha(out / "environment.json"),
              "annotation_hashes_sha256": sha(out / "annotation_hashes.json"),
              "memberships_sha256": sha(out / "memberships.csv.gz")}
    manifest = {"schema": "historical_pilot_sampling_run_v1", "status": "prepared_no_scores",
                "prepared_utc": campaign.utc(), "git_commit": campaign.git("rev-parse", "HEAD"),
                "run_fingerprint": fingerprint(frozen), **frozen,
                "main_logical_evaluations": 320, "estimator_panel_logical_evaluations": 40,
                "physical_fits_planned": sum(j["reuse_from"] is None for j in jobs),
                "historical_graph_n": 7080, "test_n": 1082, "test_proxy_positive": 21,
                "train_n": 1179, "train_proxy_positive": 31,
                "comparative_gate_unchanged": True, "external_scores_computed": False}
    dump(out / "manifest.json", manifest)
    print(json.dumps({k: manifest[k] for k in ("status", "run_fingerprint", "physical_fits_planned")}), flush=True)


def validate_run(out):
    manifest = json.loads((out / "manifest.json").read_text())
    frozen_keys = ("config_sha256", "input_hashes", "source_hashes", "environment_sha256",
                   "annotation_hashes_sha256", "memberships_sha256")
    if manifest["run_fingerprint"] != fingerprint({k: manifest[k] for k in frozen_keys}):
        raise ValueError("Frozen manifest fingerprint changed")
    campaign.verify_hashes(out, {"config.json": manifest["config_sha256"],
                                "environment.json": manifest["environment_sha256"],
                                "annotation_hashes.json": manifest["annotation_hashes_sha256"],
                                "memberships.csv.gz": manifest["memberships_sha256"]})
    campaign.verify_hashes(ROOT, manifest["source_hashes"])
    campaign.verify_hashes(out / "code_snapshot", manifest["source_hashes"])
    campaign.verify_hashes(ROOT, manifest["input_hashes"])
    old_env, env = json.loads((out / "environment.json").read_text()), campaign.environment()
    if old_env["packages"] != env["packages"] or old_env["python_major_minor"] != env["python_major_minor"]:
        raise ValueError("Execution dependencies changed")
    pop, test, pools, labels, used = original_inputs()
    if used != json.loads((out / "annotation_hashes.json").read_text()):
        raise ValueError("Annotations changed")
    config = json.loads((out / "config.json").read_text())
    validate_config(config, make_jobs(pools, test))
    sources = {int(row.file_id): campaign.source_path(row.path).read_text(encoding="utf-8", errors="replace")
               for row in pop.itertuples()}
    return config, manifest, sources, labels


def distribution(values):
    a = np.asarray(values, dtype=float)
    a = a[np.isfinite(a)]
    if not len(a):
        return {k: None for k in ("mean", "sd", "min", "q025", "q25", "median", "q75", "q975", "max")}
    return {"mean": float(a.mean()), "sd": float(a.std(ddof=1)) if len(a) > 1 else None,
            **dict(zip(("min", "q025", "q25", "median", "q75", "q975", "max"),
                       map(float, np.quantile(a, [0, .025, .25, .5, .75, .975, 1]))))}


def aggregate(out, config, manifest):
    rows, workload, resources = [], [], []
    for job in config["jobs"]:
        result_path = out / "fits" / job["job_id"] / "result.json"
        if not result_path.exists():
            continue
        result = campaign.checked_result(result_path, manifest["run_fingerprint"])
        evaluation = json.loads((result_path.parent / result["evaluation_path"]).read_text())
        resource = json.loads((result_path.parent / result["resources_path"]).read_text())
        ident = {k: job[k] for k in ("job_id", "panel", "draw", "estimator_seed", "regime", "method", "training_membership_sha256")}
        base = {**ident, "status": result["status"], "physical_fit": result["physical_fit"],
                "reuse_from": job["reuse_from"], "scoring_coverage": evaluation["scoring_coverage"]}
        rows.append({**base, "ap_proxy": evaluation["ranking_ap"],
                     "trapezoidal_pr_area_proxy": evaluation["ranking_trapezoidal_pr_area"]})
        resources.append({**base, **{k: resource.get(k) for k in ("total_seconds", "fit_seconds", "train_preprocessing_seconds",
                         "test_preprocessing_seconds", "predict_seconds", "process_peak_rss_mib_cumulative", "convergence_warning")},
                         "error": json.dumps(result["error"])})
        workload.extend({**base, **b} for b in evaluation["budgets"])
    summary = out / "summary"
    summary.mkdir(exist_ok=True)
    ranking, work = pd.DataFrame(rows), pd.DataFrame(workload)
    ranking.to_csv(summary / "per_evaluation_ranking.csv", index=False)
    work.to_csv(summary / "per_evaluation_workload.csv", index=False)
    pd.DataFrame(resources).to_csv(summary / "runtime_failures.csv", index=False)
    long = []
    for r in rows:
        long.append({**r, "metric": "ap_proxy", "budget": 0.0, "value": r["ap_proxy"]})
    for w in workload:
        for metric in ("known_positive_reviewed_expected", "known_positive_recall_expected", "judged_precision_ratio_of_expected_counts"):
            long.append({**w, "metric": metric, "budget": w["review_fraction_requested"], "value": w[metric]})
    data = pd.DataFrame(long)
    summaries, pairs = [], []
    if len(data):
        for keys, part in data.groupby(["panel", "regime", "method", "metric", "budget"], dropna=False):
            good = part[part.status != "failed"]
            summaries.append({**dict(zip(("panel", "regime", "method", "metric", "budget"), keys)),
                              "n_evaluations": len(part), "n_failed": int((part.status == "failed").sum()),
                              "n_distinct_training_memberships": part.training_membership_sha256.nunique(),
                              **distribution(good.value), "interpretation": "descriptive_conditional_no_inferential_CI"})
        main = data[data.panel == "training_draw"]
        for (method, metric, budget), part in main.groupby(["method", "metric", "budget"]):
            for left, right in itertools.combinations(REGIMES, 2):
                a = part[(part.regime == left) & (part.status != "failed")].set_index("draw")
                b = part[(part.regime == right) & (part.status != "failed")].set_index("draw")
                shared = a.index.intersection(b.index)
                differences = a.loc[shared, "value"].astype(float) - b.loc[shared, "value"].astype(float)
                for draw, difference in differences.items():
                    pairs.append({"method": method, "metric": metric, "budget": budget, "draw": int(draw),
                                  "left_regime": left, "right_regime": right, "difference_left_minus_right": difference})
    pd.DataFrame(summaries).to_csv(summary / "conditional_distributions.csv", index=False)
    paired = pd.DataFrame(pairs)
    paired.to_csv(summary / "paired_draw_differences.csv", index=False)
    paired_summary = []
    if len(paired):
        keys = ["method", "metric", "budget", "left_regime", "right_regime"]
        for key, part in paired.groupby(keys):
            values = part.difference_left_minus_right
            paired_summary.append({**dict(zip(keys, key)), "n_paired_successful_draws": len(part),
                                   **distribution(values), "fraction_positive_descriptive": float((values > 0).mean()),
                                   "interpretation": "paired_training_draw_variation_fixed_T_no_p_value_no_new_family_CI"})
    pd.DataFrame(paired_summary).to_csv(summary / "paired_difference_distributions.csv", index=False)
    return rows


def run(out, max_fits=None):
    config, manifest, sources, labels = validate_run(out)
    manifest.update(status="running_conditional_diagnostic", scoring_started_utc=manifest.get("scoring_started_utc", campaign.utc()))
    dump(out / "manifest.json", manifest)
    physical = 0
    for job in config["jobs"]:
        path = out / "fits" / job["job_id"] / "result.json"
        if path.exists():
            campaign.checked_result(path, manifest["run_fingerprint"])
            continue
        if max_fits is not None and physical >= max_fits:
            break
        reuse = None
        if job["reuse_from"]:
            reuse = campaign.checked_result(out / "fits" / job["reuse_from"] / "result.json", manifest["run_fingerprint"])
        result = campaign.publish_job(out, job, config, manifest, sources, labels, reuse_result=reuse)
        physical += int(reuse is None)
        print(json.dumps({"job": job["job_id"], "panel": job["panel"], "draw": job["draw"],
                          "regime": job["regime"], "method": job["method"], "status": result["status"],
                          "physical_fits_this_invocation": physical}), flush=True)
        gc.collect()
    rows = aggregate(out, config, manifest)
    complete = len(rows) == len(config["jobs"])
    if complete:
        from random_ranking_reference import random_ranking_reference
        reference = random_ranking_reference(1082, 21, n_draws=10000, seed=20261025)
        dump(out / "summary/random_ranking_reference.json", reference)
    manifest.update(status="complete_conditional_diagnostic" if complete else "partial_conditional_diagnostic",
                    last_updated_utc=campaign.utc(), evaluations_complete=len(rows),
                    physical_fits_complete=sum(r["physical_fit"] for r in rows),
                    failed_evaluations=sum(r["status"] == "failed" for r in rows),
                    summary_hashes={str(p.relative_to(out)): sha(p) for p in (out / "summary").iterdir() if p.is_file()})
    dump(out / "manifest.json", manifest)
    print(json.dumps({k: manifest[k] for k in ("status", "evaluations_complete", "physical_fits_complete", "failed_evaluations")}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "run"))
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--max-fits", type=int)
    args = parser.parse_args()
    if args.max_fits is not None and args.max_fits < 0:
        parser.error("--max-fits must be nonnegative")
    os.chdir(ROOT)
    if args.action == "prepare":
        prepare(args.out)
    else:
        run(args.out, args.max_fits)


if __name__ == "__main__":
    main()
