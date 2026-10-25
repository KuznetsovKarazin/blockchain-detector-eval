"""Create a one-seed bundle for runner integration on the ALREADY SCORED pilot.

This adapter is not a new test selection or a main-study design. Its only
purpose is to exercise preparation/resume on existing development artifacts.
"""
import argparse
import json
from pathlib import Path
import shutil

import pandas as pd

import run_development as runner


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pilot", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    if a.out.exists():
        raise FileExistsError(a.out)
    original = json.loads((a.pilot / "manifest.json").read_text())
    if original["status"] != "complete_development_only":
        raise ValueError("Only the completed development pilot is accepted")
    for name, key in (("memberships.csv", "membership_sha256"), ("source_inventory.csv", "source_inventory_sha256"),
                      ("label_input_hashes.json", "label_inputs_sha256")):
        if runner.sha(a.pilot / name) != original[key]:
            raise ValueError(f"Changed original pilot input: {name}")
    members = pd.read_csv(a.pilot / "memberships.csv")
    members["test_id"] = "already_scored_pilot_T"
    members["class"] = "reentrancy"
    members["seed"] = 0
    members.loc[members.role == "test", "class"] = "*"
    members.loc[members.role == "test", "seed"] = -1
    a.out.mkdir(parents=True)
    members.to_csv(a.out / "selected_memberships.csv", index=False)
    for name in runner.BASE_BUNDLE:
        shutil.copy2(a.pilot / name, a.out / name)
    manifest = {"schema": "security_runner_integration_bundle_v1", "purpose": "development_only",
                "external_scoring_allowed": False, "train_allowed": True,
                "decision": "Runner integration only on the previously scored pilot; not the selected main campaign",
                "data_commits": {"DAppSCAN": runner.DAPP_PIN}, "membership_file": "selected_memberships.csv",
                "permitted_test_ids": ["already_scored_pilot_T"], "seeds": [0], "classes": ["reentrancy"],
                "origin_pilot_manifest_sha256": runner.sha(a.pilot / "manifest.json"),
                "adapter_source_sha256": runner.sha(Path(__file__)),
                "hashes": {n: runner.sha(a.out / n) for n in ("selected_memberships.csv", *runner.BASE_BUNDLE)}}
    runner.dump(a.out / "design_manifest.json", manifest)


if __name__ == "__main__":
    main()
