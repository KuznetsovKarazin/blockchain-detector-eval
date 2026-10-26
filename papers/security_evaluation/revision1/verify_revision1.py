"""Post-result independent arithmetic/provenance checks; no model fits.

This verifier is not the generating implementation. It deletes every vertex
from one saved contracted graph and recomputes components with SciPy, checks
the probability packet and independently reconstructs AP/workload arithmetic.
Pending modules are reported as pending, never as verified completed results.
Private sample keys are read only if present; no row-level keys are emitted.
"""
from __future__ import annotations
import argparse
import gzip
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

ROOT = Path(__file__).resolve().parents[3]
REV = ROOT / "papers/security_evaluation/revision1"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def hashes(base, mapping):
    for name, expected in mapping.items():
        assert sha(Path(base) / name) == expected, name


def graph_mechanism():
    run = REV / "graph_mechanism/run_20261025_v1"
    summary = read(run / "summary.json")
    hashes(run, summary["output_sha256"])
    vertices = pd.read_csv(run / "contracted_vertices_string_aware_full_upstream_21950_080.csv")
    edges = pd.read_csv(run / "contracted_edges_string_aware_full_upstream_21950_080.csv.gz")
    arts = pd.read_csv(run / "articulation_projects.csv")
    bridges = pd.read_csv(run / "bridges.csv")
    def chosen(frame):
        return frame[(frame.normalization == "string_aware") &
                     (frame.cohort == "full_upstream_21950") & (frame.threshold == 0.8)]
    actual = chosen(arts).set_index("vertex")
    actual_bridges = chosen(bridges)
    n = len(vertices)
    assert vertices.vertex.tolist() == list(range(n))
    weights = vertices.dapp_files.to_numpy()
    adjacency = coo_matrix((np.ones(2 * len(edges)),
        (np.r_[edges.left_vertex, edges.right_vertex], np.r_[edges.right_vertex, edges.left_vertex])),
        shape=(n, n)).tocsr()
    _, original = connected_components(adjacency, directed=False)
    computed = {}
    for vertex in range(n):
        remaining = np.flatnonzero((original == original[vertex]) & (np.arange(n) != vertex))
        _, components = connected_components(adjacency[remaining][:, remaining], directed=False)
        pieces = np.bincount(components, weights=weights[remaining])
        positive = pieces[pieces > 0].astype(int)
        if len(positive) > 1:
            computed[vertex] = (int(sum(positive) - max(positive)),
                               int((sum(positive) ** 2 - sum(positive * positive)) // 2))
    assert set(computed) == set(actual.index)
    for vertex, (separated, pairs) in computed.items():
        assert actual.at[vertex, "separated_dapp_files"] == separated
        assert actual.at[vertex, "disconnected_dapp_pairs"] == pairs
    for row in actual_bridges.itertuples():
        altered = adjacency.tolil(copy=True)
        altered[row.left_vertex, row.right_vertex] = 0
        altered[row.right_vertex, row.left_vertex] = 0
        _, components = connected_components(altered.tocsr(), directed=False)
        assert components[row.left_vertex] != components[row.right_vertex]
        left = int(weights[components == components[row.left_vertex]].sum())
        right = int(weights[components == components[row.right_vertex]].sum())
        assert min(left, right) == row.smaller_side_dapp_files
        assert left * right == row.disconnected_dapp_pairs
    curves = pd.read_csv(run / "component_curves.csv")
    main = curves[(curves.normalization == "string_aware") & (curves.policy == "joint") &
                  (curves.cohort == "full_dappscan_21457")].set_index("threshold")
    assert main.at[0.8, "files"] == 21457 and main.at[0.8, "giant_files"] == 20588
    assert main.at[1.0, "giant_files"] == 19321
    return {"status": "pass", "source_summary_sha256": sha(run / "summary.json"),
            "independent_vertex_deletions": n, "weighted_articulation_projects": len(computed),
            "reported_bridges_deleted_and_verified": len(actual_bridges), "simple_links": len(edges),
            "max_separated_dapp_files_after_project_removal": max(x[0] for x in computed.values()),
            "full_dappscan_denominator": 21457, "giant_at_080": 20588, "giant_at_100": 19321,
            "interpretation": "Project deletion, not a claim about individual file bridges; full denominator differs from historical projection"}


def identity_controls():
    """Independent union-find over project and hash buckets; no saved edges used."""
    run = REV / "graph_mechanism/identity_controls_20261025_v1"
    hashes(run, read(run / "summary.json")["output_sha256"])
    nodes = pd.read_csv(ROOT / "papers/security_evaluation/dependency_audit/string_aware_recovered_20261025/nodes.csv",
                        keep_default_na=False)
    nodes = nodes[nodes.dataset.eq("dappscan")]
    saved = pd.read_csv(run / "memberships.csv.gz")
    saved = saved[(saved.normalization == "string_aware") & (saved.cohort == "full_dappscan_21457")]
    result = {}
    for variant in ["project_raw_equality", "project_normalized_stream_nonempty", "project_normalized_stream_with_empty"]:
        parent = {int(i): int(i) for i in nodes.node_id}
        def root(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i
        for column in ["project_id", "file_sha256"] + ([] if variant == "project_raw_equality" else ["normalized_sha256"]):
            selected = nodes
            if column == "normalized_sha256" and variant.endswith("nonempty"):
                selected = nodes[nodes[column] != hashlib.sha256(b"").hexdigest()]
            for _, group in selected.groupby(column):
                first, *others = map(int, group.node_id)
                for item in others:
                    left, right = root(first), root(item)
                    parent[max(left, right)] = min(left, right)
        calculated = np.asarray([root(int(i)) for i in nodes.node_id])
        existing = saved[saved.variant == variant].set_index("node_id").loc[nodes.node_id, "component"].to_numpy()
        assert np.array_equal(calculated, existing)
        sizes = np.unique(calculated, return_counts=True)[1]
        result[variant] = {"files": len(nodes), "components": len(sizes), "giant_files": int(sizes.max())}
    assert [result[x]["giant_files"] for x in result] == [3608, 19298, 19321]
    return {"status": "pass", "method": "Independent union-find on hash/project groups, no recorded graph edges",
            "scope": "string-aware full 21457-file DAppSCAN", "controls": result,
            "source_summary_sha256": sha(run / "summary.json")}


def probability_packet():
    run = REV / "external_protocol/packet_probability_20261025_v1"
    manifest = read(run / "packet_manifest.json")
    hashes(run, read(run / "public_file_hashes.json"))
    allocation = pd.read_csv(run / "stratum_allocation.csv")
    assert allocation.N_h.sum() == 3996 and allocation.n_h.sum() == 180 and len(allocation) == 17
    assert np.allclose(allocation.inclusion_probability, allocation.n_h / allocation.N_h)
    assert np.allclose(allocation.design_weight, allocation.N_h / allocation.n_h)
    assert ((allocation.n_h >= 2) | (allocation.n_h == allocation.N_h)).all()
    for name in ["reviewer_1_blank.csv", "reviewer_2_blank.csv"]:
        blank = pd.read_csv(run / name, keep_default_na=False)
        assert len(blank) == 180 and blank.iloc[:, 3:].eq("").all().all()
    blank = pd.read_csv(run / "adjudication_blank.csv", keep_default_na=False)
    assert blank.iloc[:, 2:].eq("").all().all()
    train = pd.read_csv(run / "training_manifest.csv")
    test = pd.read_csv(run / "external_cohort_manifest.csv")
    assert len(train) == 691 and len(test) == 1998 and not set(train.component) & set(test.address_expanded_080)
    private = ROOT / manifest["private_data_root"]
    key = private / "coordinator_sampling_key.csv"
    replay = None
    if key.exists():
        assert sha(key) == manifest["private_sampling_key_sha256"]
        sample = pd.read_csv(key)
        assert len(sample) == 180 and sample.path.nunique() == 170
        assert not sample[["path", "class"]].duplicated().any()
        frame = pd.read_csv(ROOT / "data/derived/security_external_recovered_20261025/provisional_label_manifest.csv",
                            keep_default_na=False).merge(test[["path", "source_id"]], on="path", validate="many_to_one")
        rng, selected = np.random.default_rng(2026102501), []
        for source, cls, status, N, n, probability, weight in allocation.itertuples(index=False, name=None):
            group = frame[(frame.source_id == source) & (frame["class"] == cls) &
                          (frame.label_status == status)].sort_values("path")
            assert len(group) == N
            chosen = group.iloc[np.sort(rng.choice(N, size=n, replace=False))]
            selected.extend(chosen[["path", "class"]].itertuples(index=False, name=None))
        order = rng.permutation(len(selected))
        assert [selected[i] for i in order] == list(sample[["path", "class"]].itertuples(index=False, name=None))
        replay = True
    return {"status": "pass", "source_manifest_sha256": sha(run / "packet_manifest.json"),
            "case_frame": 3996, "probability_cases": 180, "unique_files": 170, "strata": 17,
            "inclusion_probabilities_and_weights_match": True, "independent_sampling_replay": replay,
            "both_review_forms_and_adjudication_blank": True, "human_judgments_completed": 0,
            "train_test_component_overlap": 0}


def representations():
    run = REV / "representations/run_20261025_v1"
    manifest = read(run / "manifest.json")
    metadata = pd.read_csv(run / "representation_metadata.csv", keep_default_na=False)
    nodes = pd.read_csv(run / "nodes_unchanged.csv", keep_default_na=False)
    original = pd.read_csv(ROOT / "papers/security_evaluation/dependency_audit/string_aware_recovered_20261025/nodes.csv",
                           keep_default_na=False)
    assert nodes.equals(original) and len(nodes) == 24131 and int(nodes.candidate_test.sum()) == 1998
    assert metadata.path.equals(nodes.path) and metadata.file_sha256.equals(nodes.file_sha256)
    result = {"status": "pending_graph_completion", "nodes_and_raw_hashes_unchanged": True,
              "nodes": len(nodes), "candidate_files": 1998,
              "structural_scan_errors": int(metadata.structural_scan_error.ne("").sum()),
              "variants": []}
    if manifest["status"] != "complete_unscored_representation_sensitivity":
        return result
    hashes(run, manifest["common_output_hashes"])
    for folder in sorted(run.iterdir()):
        if not folder.is_dir() or not (folder / "summary.json").exists():
            continue
        summary = read(folder / "summary.json")
        if "representation" not in summary:
            continue
        hashes(folder, summary["output_hashes"])
        member = pd.read_csv(folder / "memberships.csv.gz")
        with np.load(folder / "lexical_edges.npz") as pairs:
            sizes = pairs["node_shingle_sizes"]
            left, right = pairs["left"], pairs["right"]
            assert len(sizes) == 24131
            assert (sizes[left] > 0).all() and (sizes[right] > 0).all()
            assert np.array_equal(member.informative_representation, sizes > 0)
        result["variants"].append({"representation": summary["representation"],
                                   "informative_nodes": int(member.informative_representation.sum()),
                                   "unavailable_nodes": int((~member.informative_representation).sum()),
                                   "unavailable_nodes_have_no_lexical_edges": True})
    assert len(result["variants"]) == 4
    result["status"] = "pass"
    result["source_manifest_sha256"] = sha(run / "manifest.json")
    return result


def segmented_control():
    run = REV / "representations/segmented_control_20261025_v1"
    manifest = read(run / "manifest.json")
    if manifest["status"] != "complete_posthoc_unscored_control":
        return {"status": "pending_segmented_control_completion"}
    config = read(run / "config_before_outputs.json")
    assert sha(run / "config_before_outputs.json") == manifest["config_sha256"]
    hashes(run / "executed_source", config["code_hashes"])
    original = ROOT / config["original_run"]
    for name in ["nodes_unchanged.csv", "structural_edges_unchanged.csv"]:
        assert sha(run / name) == sha(original / name)
    diagnostics = pd.read_csv(run / "boundary_diagnostics.csv")
    reports, samples = [], {}
    for index, variant in enumerate(config["variants"]):
        folder = run / variant
        hashes(folder, read(folder / "summary.json")["output_hashes"])
        rows = diagnostics[diagnostics.representation == variant].sort_values("node_id").set_index("node_id")
        assert len(rows) == 24131
        with np.load(folder / "lexical_edges.npz") as edges:
            sizes, left, right = edges["node_shingle_sizes"], edges["left"], edges["right"]
            assert np.array_equal(sizes, rows.segmented_shingles)
            assert (sizes[left] > 0).all() and (sizes[right] > 0).all()
        assert (rows.segmented_shingles <= rows.concatenated_shingles).all()
        assert np.array_equal(rows.concatenated_shingles - rows.segmented_shingles,
                              rows.boundary_only_unique_shingles_removed)
        eligible = rows.index[rows.boundary_only_unique_shingles_removed > 0].to_numpy()
        sample = eligible[np.linspace(0, len(eligible) - 1, min(40, len(eligible)), dtype=int)]
        samples[index] = (set(map(int, sample)), rows)
        reports.append({"representation": variant, "changed_shingle_files": len(eligible),
                        "sampled_changed_files_for_independent_windows": len(sample),
                        "empty_nodes_have_no_lexical_edges": True})
    with gzip.open(ROOT / config["private_cache"] / "segments.jsonl.gz", "rt") as stream:
        for node, line in enumerate(stream):
            if not any(node in selected for selected, rows in samples.values()):
                continue
            variants = json.loads(line)
            for index, (selected, rows) in samples.items():
                if node not in selected:
                    continue
                tokens, source_segments = [], []
                for segment, text in enumerate(variants[index]):
                    words = text.split()
                    tokens.extend(words)
                    source_segments.extend([segment] * len(words))
                all_windows, valid_windows = set(), set()
                for start in range(max(1, len(tokens) - 4)) if tokens else []:
                    end = min(start + 5, len(tokens))
                    window = tuple(tokens[start:end])
                    all_windows.add(window)
                    if len(set(source_segments[start:end])) == 1:
                        valid_windows.add(window)
                assert len(all_windows) == rows.at[node, "concatenated_shingles"]
                assert len(valid_windows) == rows.at[node, "segmented_shingles"]
    return {"status": "pass", "config_sha256": manifest["config_sha256"],
            "nodes_and_structural_edges_unchanged": True,
            "common_output_hashes": {name: sha(run / name) for name in
                                     ["nodes_unchanged.csv", "structural_edges_unchanged.csv", "boundary_diagnostics.csv"]},
            "variants": reports,
            "interpretation": "Post hoc implementation control; shingle removal can add similarity edges by shrinking denominators"}


def sampling():
    run = REV / "sampling_variance/run_20261025_v2"
    manifest = read(run / "manifest.json")
    if manifest["status"] != "complete_conditional_diagnostic":
        return {"status": "pending_sampling_completion", "run_fingerprint": manifest["run_fingerprint"]}
    hashes(ROOT, manifest["source_hashes"])
    hashes(run / "code_snapshot", manifest["source_hashes"])
    hashes(ROOT, manifest["input_hashes"])
    hashes(run, manifest["summary_hashes"])
    assert sha(run / "config.json") == manifest["config_sha256"]
    config = read(run / "config.json")
    assert len(config["jobs"]) == 360 and manifest["physical_fits_complete"] == 282
    inventory = pd.read_csv(ROOT / "papers/security_evaluation/runs/dev_fixed_t_20261025_v1/source_inventory.csv").set_index("file_id")
    test_ids = config["jobs"][0]["test_ids"]
    targets = []
    prefix = "data/raw/DAppSCAN/DAppSCAN-source/contracts/"
    for file_id in test_ids:
        path = inventory.at[file_id, "path"]
        assert path.startswith(prefix)
        annotation = ROOT / "data/raw/DAppSCAN/DAppSCAN-source/SWCsource" / Path(path[len(prefix):]).with_suffix(".json")
        categories = [x.get("category", "") for x in read(annotation).get("SWCs", [])] if annotation.exists() else []
        targets.append(int(any(value.startswith("SWC-107") for value in categories)))
    y = np.asarray(targets)
    assert len(y) == 1082 and y.sum() == 21
    checked_ap = checked_workload = failed = 0
    for job in config["jobs"]:
        assert job["test_ids"] == test_ids
        folder = run / "fits" / job["job_id"]
        result = read(folder / "result.json")
        assert result["run_fingerprint"] == manifest["run_fingerprint"]
        hashes(folder, result["artifact_hashes"])
        pred = pd.read_csv(folder / result["predictions_path"], float_precision="round_trip")
        evaluation = read(folder / result["evaluation_path"])
        assert pred.file_id.tolist() == test_ids
        if result["status"] == "failed":
            assert pred.score.isna().all() and evaluation["ranking_ap"] is None
            failed += 1
            continue
        score = pred.score.to_numpy()
        assert np.isfinite(score).all() and pred.status.eq("ok").all()
        order = np.argsort(-score, kind="stable")
        ranked, labels = score[order], y[order]
        endpoints = np.flatnonzero(np.r_[ranked[:-1] != ranked[1:], True])
        cumulative = np.cumsum(labels)[endpoints]
        additions = np.diff(np.r_[0, cumulative])
        ap = float(np.sum(additions * cumulative / (endpoints + 1)) / y.sum())
        assert np.isclose(ap, evaluation["ranking_ap"], rtol=1e-12, atol=1e-15)
        checked_ap += 1
        for budget in evaluation["budgets"]:
            k = budget["review_count_requested"]
            if k == 0:
                expected = 0.0
            else:
                boundary = ranked[k - 1]
                above, tied = ranked > boundary, ranked == boundary
                expected = float(labels[above].sum() + (k - above.sum()) * labels[tied].mean())
            assert np.isclose(expected, budget["known_positive_reviewed_expected"], rtol=1e-12, atol=1e-15)
            checked_workload += 1
    random = read(run / "summary/random_ranking_reference.json")
    assert random["n_draws"] == 10000 and random["inferential_p_values_computed"] is False
    assert [row["review_count"] for row in random["workload"]] == [54, 108, 216]
    return {"status": "pass", "run_fingerprint": manifest["run_fingerprint"],
            "logical_evaluations": len(config["jobs"]), "physical_fits": 282,
            "independent_ap_recalculations": checked_ap, "independent_tie_workload_recalculations": checked_workload,
            "failed_evaluations": failed, "random_ranking_exact_ap_mean": random["exact_ap_mean"],
            "interpretation": "Fixed historical test; conditional training variation, not independent project inference"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=REV / "independent_verification.json")
    args = parser.parse_args()
    checks = {"graph_mechanism": graph_mechanism(), "identity_controls": identity_controls(), "probability_packet": probability_packet(),
              "representations": representations(), "segmented_control": segmented_control(), "sampling": sampling()}
    report = {"schema": "revision1_independent_verification_v1", "created_utc": datetime.now(timezone.utc).isoformat(),
              "verifier_sha256": sha(Path(__file__)), "no_model_fits_performed_by_verifier": True,
              "human_expert_review": False, "checks": checks,
              "status": "pass" if all(x["status"] == "pass" for x in checks.values()) else "partial_pending_modules"}
    args.out.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
