"""
00  Fetch the public datasets used by all experiments, pinned to exact commits.

Everything here is downloaded from public GitHub repositories (shallow clone
+ checkout of the pinned commit). Git LFS objects are NOT needed for any of
these sources.

Datasets that cannot be redistributed or fetched automatically are listed at
the end with manual instructions (Elliptic, Elliptic++).

Usage
-----
    python scripts/00_fetch_data.py               # all sources
    python scripts/00_fetch_data.py --only xchainwatcher smartbugs-curated
"""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path

RAW = Path(__file__).resolve().parents[1] / "data" / "raw"

SOURCES = {
    # name: (repo, commit, used by)
    "XChainWatcher": ("AndreAugusto11/XChainWatcher", "4cc1ff173c18f80d275d7af6cbd318cdd3906e77", "B"),
    "smartbugs-curated": ("smartbugs/smartbugs-curated", "230e649123477eff332742a59a1c7cc6dc286cab", "C"),
    "SolidiFI-benchmark": ("DependableSystemsLab/SolidiFI-benchmark", "4b0573e1b3f7031396de6f48f7f3e7380222ad3a", "C"),
    "DAppSCAN": ("InPlusLab/DAppSCAN", "66a56619c44770e05c2db600fa6468115ff0dcd5", "C"),
}

MANUAL = """
Manual downloads (licence / hosting does not allow scripted download):

  Elliptic (Weber et al. 2019) -> data/raw/elliptic/
      https://www.kaggle.com/datasets/ellipticco/elliptic-data-set
      files: elliptic_txs_features.csv, elliptic_txs_classes.csv, elliptic_txs_edgelist.csv

  Elliptic++ (Elmougy & Liu 2023) -> data/raw/ellipticpp/   (optional)
      https://github.com/git-disl/EllipticPlusPlus  (Google Drive link in README)
"""


def fetch(name: str, repo: str, commit: str) -> None:
    dst = RAW / name
    if (dst / ".git").exists() or dst.is_symlink():
        print(f"[skip] {name} already present")
        return
    env = dict(os.environ, GIT_LFS_SKIP_SMUDGE="1")
    subprocess.run(["git", "init", "-q", str(dst)], check=True)
    subprocess.run(["git", "-C", str(dst), "remote", "add", "origin", f"https://github.com/{repo}"], check=True)
    subprocess.run(["git", "-C", str(dst), "fetch", "-q", "--depth", "1", "origin", commit], check=True, env=env)
    subprocess.run(["git", "-C", str(dst), "checkout", "-q", "FETCH_HEAD"], check=True, env=env)
    print(f"[ok]   {name} @ {commit[:8]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*")
    a = ap.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)
    for name, (repo, commit, _) in SOURCES.items():
        if a.only and name not in a.only:
            continue
        fetch(name, repo, commit)
    print(MANUAL)


if __name__ == "__main__":
    main()
