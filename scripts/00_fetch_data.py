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
    "DeFiHackLabs": ("SunWeb3Sec/DeFiHackLabs", "23c7bd83ccb4524972a9493617fcc8764ab6269b", "K4"),
}

MANUAL = """
Manual downloads (licence / hosting does not allow scripted download):

  Elliptic (Weber et al. 2019) -> data/raw/elliptic/
      https://www.kaggle.com/datasets/ellipticco/elliptic-data-set
      files: elliptic_txs_features.csv, elliptic_txs_classes.csv, elliptic_txs_edgelist.csv

  Elliptic++ (Elmougy & Liu 2023) -> data/raw/ellipticpp/   (optional)
      https://github.com/git-disl/EllipticPlusPlus  (Google Drive link in README)
"""


def _git(dst: Path, *args: str) -> str | None:
    r = subprocess.run(["git", "-C", str(dst), *args], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def checkout_state(dst: Path, commit: str) -> str:
    """'missing', 'pinned' (HEAD at the pin, clean), 'modified' (HEAD at the pin,
    local changes), 'incomplete' (no HEAD, e.g. an interrupted download),
    'other_commit' (clean checkout of another revision), 'other_modified'
    (another revision with local changes) or 'not_git'."""
    if not dst.exists():
        return "missing"
    if not (dst / ".git").exists():
        return "not_git"
    head = _git(dst, "rev-parse", "--verify", "-q", "HEAD")
    if not head:
        return "incomplete"
    dirty = bool(_git(dst, "status", "--porcelain", "--untracked-files=no"))
    if head == commit:
        return "modified" if dirty else "pinned"
    return "other_modified" if dirty else "other_commit"


def fetch(name: str, repo: str, commit: str) -> None:
    dst = RAW / name
    state = checkout_state(dst.resolve(), commit)
    if state == "pinned":
        print(f"[ok]   {name} already at {commit[:8]}")
        return
    if state == "modified":
        print(f"[warn] {name} at {commit[:8]} with local changes; left as is")
        return
    if state in ("other_modified", "not_git"):
        raise SystemExit(f"{dst}: {state.replace('_', ' ')}; expected a clean checkout of {commit}. "
                         "Move it away (local changes are not overwritten) and run again.")
    env = dict(os.environ, GIT_LFS_SKIP_SMUDGE="1")
    if state == "missing":
        subprocess.run(["git", "init", "-q", str(dst)], check=True)
    if _git(dst, "remote", "get-url", "origin") is None:
        subprocess.run(["git", "-C", str(dst), "remote", "add", "origin", f"https://github.com/{repo}"], check=True)
    subprocess.run(["git", "-C", str(dst), "fetch", "-q", "--depth", "1", "origin", commit], check=True, env=env)
    subprocess.run(["git", "-C", str(dst), "checkout", "-q", "FETCH_HEAD"], check=True, env=env)
    if checkout_state(dst, commit) != "pinned":
        raise SystemExit(f"{dst}: checkout did not reach {commit}")
    print(f"[ok]   {name} @ {commit[:8]} ({'resumed' if state == 'incomplete' else 'updated' if state == 'other_commit' else 'fetched'})")


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
