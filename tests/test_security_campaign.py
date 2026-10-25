"""Scientific and resume guards for the development campaign runner."""
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

SPEC = importlib.util.spec_from_file_location(
    "security_campaign", Path(__file__).parents[1] / "papers/security_evaluation/campaign/run_development.py")
campaign = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(campaign)


def valid_fixture():
    # A -> clone x -> B -> clone z -> C is one transitive component.
    inv = pd.DataFrame({"file_id": range(9), "dataset": ["dappscan"]*9,
                        "path": [f"{campaign.PREFIX}{i}.sol" for i in range(9)],
                        "group": ["A", "A", "B", "B", "C", "D", "D", "E", "E"],
                        "comp": ["x", "y", "x", "z", "z", "d", "e", "f", "g"],
                        "joint_id": ["ABC"]*5 + ["D"]*2 + ["E"]*2})
    labels = {i: {"reentrancy": v, "unchecked": v} for i, v in enumerate([1, 0, 1, 0, 0, 1, 0, 1, 0])}
    rows = []
    for i in [0, 1]:
        rows.append({**inv.iloc[i].to_dict(), "test_id": "T", "class": "*", "seed": -1,
                     "role": "test", "regime": "common_test"})
    selected = {campaign.REGIMES[0]: [2, 3], campaign.REGIMES[1]: [2, 3],
                campaign.REGIMES[2]: [7, 8], campaign.REGIMES[3]: [5, 6]}
    for regime, ids in selected.items():
        for i in ids:
            rows.append({**inv.iloc[i].to_dict(), "test_id": "T", "class": "reentrancy", "seed": 0,
                         "role": "train", "regime": regime})
    return pd.DataFrame(rows), inv, labels


def validate(members, inv, labels):
    return campaign.validate_memberships(members, inv, labels, ["reentrancy"], [0], ["T"])


def test_valid_common_test_and_four_matched_training_regimes():
    members, inv, labels = valid_fixture()
    cells = validate(members, inv, labels)
    assert len(cells) == 4
    assert all(c["test_ids"] == [0, 1] and c["train_positive_proxy"] == 1 and c["train_n"] == 2 for c in cells)


def test_indirect_joint_bridge_is_rejected_even_without_direct_project_or_clone_overlap():
    members, inv, labels = valid_fixture()
    # C row4 shares neither project nor clone with T, but remains joint-connected.
    index = members.index[(members.role == "train") & (members.regime == campaign.REGIMES[3])][-1]
    for col in ["file_id", "path", "group", "comp", "joint_id"]:
        members.loc[index, col] = inv.loc[4, col]
    with pytest.raises(ValueError, match="joint_id overlaps"):
        validate(members, inv, labels)


def test_test_population_cannot_change_across_cells():
    members, inv, labels = valid_fixture()
    extra = members[members.role == "test"].copy()
    extra["class"], extra["seed"], extra["regime"] = "reentrancy", 0, campaign.REGIMES[0]
    extra = extra.iloc[:1]
    with pytest.raises(ValueError, match="Test population changes"):
        validate(pd.concat([members, extra]), inv, labels)


def test_exact_test_object_leak_and_unequal_training_counts_are_rejected():
    members, inv, labels = valid_fixture()
    i = members.index[(members.role == "train") & (members.regime == campaign.REGIMES[0])][0]
    for col in ["file_id", "path", "group", "comp", "joint_id"]:
        members.loc[i, col] = inv.loc[0, col]
    with pytest.raises(ValueError, match="Exact test object"):
        validate(members, inv, labels)
    members, inv, labels = valid_fixture()
    more = members[(members.role == "train") & (members.regime == campaign.REGIMES[3])].copy()
    more["regime"] = campaign.REGIMES[0]
    with pytest.raises(ValueError, match="counts differ"):
        validate(pd.concat([members, more]), inv, labels)


def test_missing_proxy_class_is_not_relaxed():
    members, inv, labels = valid_fixture()
    labels[5]["reentrancy"] = 0
    with pytest.raises(ValueError, match="Infeasible training cell"):
        validate(members, inv, labels)


@pytest.mark.parametrize("patch", [
    {"purpose": "external"}, {"external_scoring_allowed": True}, {"train_allowed": False},
    {"data_commits": {"DAppSCAN": "different"}},
])
def test_candidate_and_external_bundles_cannot_be_prepared(patch):
    good = {"purpose": "development_only", "external_scoring_allowed": False, "train_allowed": True,
            "data_commits": {"DAppSCAN": campaign.DAPP_PIN},
            "hashes": {k: "hash" for k in ["selected_memberships.csv", *campaign.BASE_BUNDLE]}}
    with pytest.raises(ValueError):
        campaign.checked_bundle_manifest({**good, **patch})


@pytest.mark.parametrize("path", ["data/raw/salzano/a.sol", "/tmp/a.sol", campaign.PREFIX + "../a.sol"])
def test_external_and_traversal_paths_rejected(path):
    with pytest.raises(ValueError):
        campaign.source_path(path)


def test_deterministic_lr_reused_only_for_identical_ordered_membership():
    members, inv, labels = valid_fixture()
    cell = validate(members, inv, labels)[0]
    same = {**cell, "seed": 1}
    different = {**cell, "seed": 2, "train_ids": [5, 6]}
    jobs = campaign.make_jobs([cell, same, different], ["raw_tfidf_lr", "pattern_rf"], list(campaign.REGIMES))
    lr = [j for j in jobs if j["method"] == "raw_tfidf_lr"]
    rf = [j for j in jobs if j["method"] == "pattern_rf"]
    assert lr[0]["reuse_from"] is None
    assert lr[1]["reuse_from"] == lr[0]["job_id"]
    assert lr[2]["reuse_from"] is None
    assert all(j["reuse_from"] is None for j in rf)


def test_result_resume_refuses_changed_prediction_or_configuration(tmp_path):
    (tmp_path / "predictions.csv").write_text("file_id,score\n1,0.5\n")
    result = {"run_fingerprint": "frozen", "status": "complete",
              "artifact_hashes": {"predictions.csv": campaign.sha(tmp_path / "predictions.csv")}}
    campaign.dump(tmp_path / "result.json", result)
    assert campaign.checked_result(tmp_path / "result.json", "frozen")["status"] == "complete"
    with pytest.raises(ValueError, match="different configuration"):
        campaign.checked_result(tmp_path / "result.json", "changed")
    (tmp_path / "predictions.csv").write_text("file_id,score\n1,0.9\n")
    with pytest.raises(ValueError, match="Hash mismatch"):
        campaign.checked_result(tmp_path / "result.json", "frozen")


def test_failed_fit_is_preserved_as_unscorable_not_safe(tmp_path, monkeypatch):
    members, inv, labels = valid_fixture()
    job = campaign.make_jobs(validate(members, inv, labels)[:1], ["raw_tfidf_lr"], list(campaign.REGIMES))[0]
    def fail(*args):
        raise RuntimeError("controlled fixture failure")
    monkeypatch.setattr(campaign, "fit_predict", fail)
    result = campaign.publish_job(tmp_path, job, {"review_fractions": [1.0]}, {"run_fingerprint": "frozen"}, {}, labels)
    folder = tmp_path / "fits" / job["job_id"]
    pred = pd.read_csv(folder / result["predictions_path"])
    evaluation = json.loads((folder / result["evaluation_path"]).read_text())
    assert pred.score.isna().all() and (pred.status == "fit_error").all()
    assert evaluation["ranking_ap"] is None
    assert evaluation["scoring_coverage"] == 0
    assert evaluation["budgets"][0]["known_positive_recall_expected"] == 0
    assert result["status"] == "failed" and (folder / "attempt_001/traceback.txt").exists()
    # An explicit retry retains the complete failed attempt.
    campaign.publish_job(tmp_path, job, {"review_fractions": [1.0]}, {"run_fingerprint": "frozen"}, {}, labels)
    assert (folder / "attempt_001/traceback.txt").exists() and (folder / "attempt_002/traceback.txt").exists()


def test_aggregation_keeps_tests_separate_and_never_pools_scores(tmp_path):
    jobs = []
    for i, (test_id, ap) in enumerate([("T1", 0.2), ("T1", 0.4), ("T2", 0.9)]):
        job = {"job_id": str(i), "test_id": test_id, "class": "reentrancy", "seed": i,
               "regime": campaign.REGIMES[0], "method": "raw_tfidf_lr",
               "training_membership_sha256": str(i), "test_joint_components": 1}
        jobs.append(job)
        folder = tmp_path / "fits" / str(i); folder.mkdir(parents=True)
        evaluation = {"ranking_ap": ap, "ranking_trapezoidal_pr_area": ap, "ranking_prevalence": 0.1,
                      "scoring_coverage": 1.0, "n_files": 10, "budgets": []}
        campaign.dump(folder / "evaluation.json", evaluation)
        campaign.dump(folder / "resources.json", {"total_seconds": 1, "convergence_warning": False})
        campaign.dump(folder / "result.json", {"run_fingerprint": "frozen", "status": "complete",
                      "evaluation_path": "evaluation.json", "resources_path": "resources.json", "physical_fit": True,
                      "artifact_hashes": {n: campaign.sha(folder/n) for n in ["evaluation.json", "resources.json"]}})
    campaign.aggregate(tmp_path, {"jobs": jobs}, {"run_fingerprint": "frozen"})
    summary = pd.read_csv(tmp_path / "summary/per_test_seed_summary.csv").set_index("test_id")
    assert set(summary.index) == {"T1", "T2"}
    assert summary.loc["T1", "mean_per_seed_ap_proxy_conditional_on_success"] == pytest.approx(0.3)
    assert summary.loc["T2", "mean_per_seed_ap_proxy_conditional_on_success"] == pytest.approx(0.9)
