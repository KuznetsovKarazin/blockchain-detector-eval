"""Scientific-scope, sampling and immutable-resume checks; no model fits."""
import copy
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

SPEC = importlib.util.spec_from_file_location("sampling_variance", Path(__file__).with_name("run_sampling_variance.py"))
sv = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sv)


@pytest.fixture(scope="module")
def jobs():
    # Three selectable pools, with precisely 31 positives in the limiting pool.
    pop = pd.DataFrame({"file_id": range(1500), "path": [f"file{i}.sol" for i in range(1500)],
                        "reentrancy": [int(i < 31 or i >= 1470) for i in range(1500)]})
    pools = {mode: pop.iloc[:size].copy() for mode, size in zip(sv.REGIMES, (1500, 1362, 1395, 1179))}
    test = pd.DataFrame({"file_id": [2000, 2001]})
    return sv.make_jobs(pools, test)


def config(jobs):
    return {"purpose": sv.PURPOSE, "external_scoring_allowed": False,
            "model_config": sv.campaign.model_config(), "jobs": jobs,
            "review_fractions": [.05, .1, .2], "n_draws": 20,
            "null_reference": {"permutations": 10000, "seed": 20261025,
                               "interpretation": "descriptive_not_inferential"}}


def test_paired_draws_and_separate_estimator_panel(jobs):
    main = [j for j in jobs if j["panel"] == "training_draw"]
    estimator = [j for j in jobs if j["panel"] == "joint_estimator_seed"]
    assert len(main) == 320 and len(estimator) == 40
    assert all(j["seed"] == j["estimator_seed"] == 0 for j in main)
    assert {j["draw"] for j in main} == set(range(20))
    assert all(j["draw"] is None and j["regime"] == sv.REGIMES[-1] for j in estimator)
    assert {j["seed"] for j in estimator} == set(range(20))
    assert {j["method"] for j in estimator} == set(sv.METHODS[2:])
    for j in main:
        assert len(j["train_ids"]) == len(set(j["train_ids"])) == 1179
        assert len([i for i in j["train_ids"] if i < 31 or i >= 1470]) == 31
        assert not set(j["train_ids"]) & set(j["test_ids"])
    for draw in range(20):
        for regime in sv.REGIMES:
            selected = [j["train_ids"] for j in main if j["draw"] == draw and j["regime"] == regime]
            assert len({tuple(x) for x in selected}) == 1  # all methods share draw


def test_joint_pool_reuse_never_counted_as_twenty_independent_draws(jobs):
    joint = [j for j in jobs if j["panel"] == "training_draw" and j["regime"] == sv.REGIMES[-1]]
    assert len({j["training_membership_sha256"] for j in joint}) == 1
    assert sum(j["reuse_from"] is None for j in joint) == 4
    lookup = {j["job_id"]: j for j in jobs}
    for job in jobs:
        if job["reuse_from"]:
            source = lookup[job["reuse_from"]]
            assert all(job[k] == source[k] for k in ("train_ids", "test_ids", "method", "estimator_seed"))
    assert sum(j["reuse_from"] is None for j in jobs) == 282


@pytest.mark.parametrize("change", ["new_test", "train", "method", "estimator_seed", "draw", "external", "parameters", "null"])
def test_scope_cannot_be_extended_by_rehashing_config(jobs, change):
    cfg = copy.deepcopy(config(jobs))
    if change == "new_test":
        cfg["jobs"][0]["test_ids"] = [99999]
    elif change == "train":
        cfg["jobs"][0]["train_ids"][0] = 99999
    elif change in ("method", "estimator_seed", "draw"):
        cfg["jobs"][0][change] = "changed"
    elif change == "external":
        cfg["external_scoring_allowed"] = True
    elif change == "parameters":
        cfg["model_config"]["lr"]["C"] = 10
    else:
        cfg["null_reference"]["interpretation"] = "inferential"
    with pytest.raises(ValueError):
        sv.validate_config(cfg, jobs)


def test_valid_frozen_design_is_accepted(jobs):
    sv.validate_config(config(jobs), jobs)


def test_config_corruption_fails_before_data_or_fit(tmp_path, monkeypatch):
    sv.dump(tmp_path / "config.json", {"changed": True})
    frozen = {"config_sha256": "old", "input_hashes": {}, "source_hashes": {},
              "environment_sha256": "old", "annotation_hashes_sha256": "old", "memberships_sha256": "old"}
    sv.dump(tmp_path / "manifest.json", {**frozen, "run_fingerprint": sv.fingerprint(frozen)})
    def forbidden():
        raise AssertionError("Data accessed before corrupted config rejected")
    monkeypatch.setattr(sv, "original_inputs", forbidden)
    with pytest.raises(ValueError, match="Hash mismatch"):
        sv.validate_run(tmp_path)


def test_result_artifact_corruption_rejected_on_resume(tmp_path):
    artifact = tmp_path / "predictions.csv"
    artifact.write_text("file_id,score,status\n1,0.5,ok\n")
    expected = sv.sha(artifact)
    sv.dump(tmp_path / "result.json", {"run_fingerprint": "frozen", "artifact_hashes": {"predictions.csv": expected}})
    sv.campaign.checked_result(tmp_path / "result.json", "frozen")
    artifact.write_text("file_id,score,status\n1,1.0,ok\n")
    with pytest.raises(ValueError):
        sv.campaign.checked_result(tmp_path / "result.json", "frozen")


def test_distribution_is_descriptive_and_handles_missing():
    actual = sv.distribution([1., 3., np.nan])
    assert actual["mean"] == 2.0
    assert actual["sd"] == pytest.approx(np.sqrt(2))
    assert actual["q025"] == pytest.approx(1.05)
    assert sv.distribution([np.nan])["mean"] is None
    assert not any("confidence" in key or "p_value" in key for key in actual)


def test_existing_result_skipped_without_refit(tmp_path, monkeypatch):
    job = {"job_id": "existing", "reuse_from": None}
    pending = {"job_id": "pending", "reuse_from": None}
    result_dir = tmp_path / "fits/existing"
    result_dir.mkdir(parents=True)
    sv.dump(result_dir / "result.json", {"run_fingerprint": "frozen", "artifact_hashes": {}})
    cfg, manifest = {"jobs": [job, pending]}, {"run_fingerprint": "frozen"}
    monkeypatch.setattr(sv, "validate_run", lambda out: (cfg, manifest, {}, {}))
    def nofit(*a, **k):
        raise AssertionError("Existing result was refit")
    monkeypatch.setattr(sv.campaign, "publish_job", nofit)
    (tmp_path / "summary").mkdir()
    monkeypatch.setattr(sv, "aggregate", lambda *a: [{"physical_fit": True, "status": "complete"}])
    sv.run(tmp_path, max_fits=0)
    assert json.loads((tmp_path / "manifest.json").read_text())["evaluations_complete"] == 1
