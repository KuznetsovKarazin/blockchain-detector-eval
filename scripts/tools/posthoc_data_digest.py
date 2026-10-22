"""
Add input-data digests to C2 runs whose manifest has an empty data field.

The digests are computed AFTER the run, from data/raw at the commits pinned by
scripts/00_fetch_data.py (recorded below); the code that selects the files is
the run's own commit. Output: <run>/manifest_data_posthoc.json.

    python scripts/tools/posthoc_data_digest.py results/contracts/<run> [...]
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from bal.data.contracts import label_files, load_all    # noqa: E402
from bal.utils.repro import atomic_write_text, corpus_digest   # noqa: E402


def repo_head(p: str) -> str | None:
    r = subprocess.run(["git", "-C", p, "rev-parse", "HEAD"], capture_output=True, text=True)
    return r.stdout.strip() or None


def main():
    df = load_all()
    sets = {f"sources_{ds}": g.path for ds, g in df.groupby("dataset")} | {"label_files": label_files()}
    out = {"computed_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "note": "computed after the run; data repositories at the commits below",
           "data_repos": {p: repo_head(p) for p in ("data/raw/smartbugs-curated", "data/raw/SolidiFI-benchmark",
                                                    "data/raw/DAppSCAN")},
           "data_sets": {k: corpus_digest(v) for k, v in sets.items()}}
    for run in sys.argv[1:]:
        atomic_write_text(Path(run) / "manifest_data_posthoc.json", json.dumps(out, indent=2))
        print("wrote", Path(run) / "manifest_data_posthoc.json")


if __name__ == "__main__":
    main()
