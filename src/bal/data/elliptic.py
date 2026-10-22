"""
Elliptic Bitcoin dataset (Weber et al. 2019, arXiv:1908.02591), used by T and K.

Files (Kaggle "ellipticco/elliptic-data-set"), expected under data/raw/elliptic/:
    elliptic_txs_features.csv   no header: txId, time_step, 93 local + 72 aggregated features
    elliptic_txs_classes.csv    txId, class in {"1" illicit, "2" licit, "unknown"}
    elliptic_txs_edgelist.csv   txId1, txId2  (all edges connect transactions of the SAME time step)

Temporal protocol used throughout the project (fixed before looking at test):

    train  time steps  1..30
    val    time steps 31..34    (early stopping, thresholds, calibration)
    test   time steps 35..49    reported as a whole and split at the dark-market
                                shutdown into 35..42 ("pre") and 43..49 ("post")

Because edges never cross time steps, the test subgraphs are disconnected from
the training subgraphs: message passing cannot leak test labels or features into
training, and graph models are inductive by construction. Feature scaling is
fitted on training nodes only.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

TRAIN_STEPS = range(1, 31)
VAL_STEPS = range(31, 35)
TEST_STEPS = range(35, 50)
PRE_SHUTDOWN = range(35, 43)
POST_SHUTDOWN = range(43, 50)

N_LOCAL = 93
N_AGG = 72


@dataclass
class Elliptic:
    tx_ids: np.ndarray          # (N,)
    step: np.ndarray            # (N,) 1..49
    X: np.ndarray               # (N, 165) float32
    y: np.ndarray               # (N,) 1 illicit, 0 licit, -1 unknown
    edges: np.ndarray           # (2, E) node indices
    feature_names: list[str]

    def mask(self, steps, labelled=True):
        m = np.isin(self.step, list(steps))
        if labelled:
            m &= self.y >= 0
        return m

    def features(self, which: str = "AF") -> np.ndarray:
        if which == "LF":
            return self.X[:, :N_LOCAL]
        if which == "AF":
            return self.X
        raise ValueError(which)


def load_elliptic(root: str | Path = "data/raw/elliptic") -> Elliptic:
    root = Path(root)
    feats = pd.read_csv(root / "elliptic_txs_features.csv", header=None)
    cls = pd.read_csv(root / "elliptic_txs_classes.csv")
    edges = pd.read_csv(root / "elliptic_txs_edgelist.csv")
    tx = feats[0].to_numpy()
    step = feats[1].to_numpy().astype(int)
    # column 1 is the time step; the remaining 165 are features (local first)
    X = feats.iloc[:, 2:].to_numpy(dtype=np.float32)
    names = [f"local_{i}" for i in range(N_LOCAL)] + [f"agg_{i}" for i in range(N_AGG)]
    lab = cls.set_index(cls.columns[0])[cls.columns[1]].astype(str).reindex(tx)
    y = np.where(lab == "1", 1, np.where(lab == "2", 0, -1)).astype(int)
    idx = pd.Series(np.arange(len(tx)), index=tx)
    e = np.vstack([idx.loc[edges.iloc[:, 0]].to_numpy(), idx.loc[edges.iloc[:, 1]].to_numpy()])
    return Elliptic(tx_ids=tx, step=step, X=X, y=y, edges=e, feature_names=names)


def make_synthetic(n_per_step: int = 400, n_steps: int = 49, seed: int = 0, shift_after: int = 42) -> Elliptic:
    """Small Elliptic-shaped synthetic set for tests and smoke runs (NOT for results)."""
    rng = np.random.default_rng(seed)
    N = n_per_step * n_steps
    step = np.repeat(np.arange(1, n_steps + 1), n_per_step)
    y = (rng.random(N) < np.where(step > shift_after, 0.01, 0.1)).astype(int)
    X = rng.normal(size=(N, N_LOCAL + N_AGG)).astype(np.float32)
    X[:, :5] += y[:, None] * 1.5
    y = np.where(rng.random(N) < 0.7, -1, y)
    src = rng.integers(0, N, 2 * N)
    dst = src + rng.integers(1, 20, 2 * N)
    ok = (dst < N) & (step[src] == step[np.clip(dst, 0, N - 1)])
    edges = np.vstack([src[ok], dst[ok]])
    names = [f"local_{i}" for i in range(N_LOCAL)] + [f"agg_{i}" for i in range(N_AGG)]
    return Elliptic(np.arange(N), step, X, y, edges, names)


def load_scores(run: str | Path, data: str | Path = "data/raw/elliptic") -> tuple[dict, np.ndarray, np.ndarray]:
    """Per-node scores of a T1 run with the labels and time steps of the scored nodes.

    The scores cover the labelled nodes in file order. Published runs do not
    redistribute Elliptic labels, so `y` / `step` are read from the local copy
    of the dataset when the score file does not carry them; `labels_sha256`
    in the file (if present) checks that the copy matches.
    """
    import hashlib
    Z = np.load(Path(run) / "scores_labelled.npz")
    scores = {k: Z[k] for k in Z.files if "|" in k}
    if "y" in Z.files:
        return scores, Z["y"], Z["step"]
    d = load_elliptic(data)
    lab = d.y >= 0
    y, step = d.y[lab], d.step[lab]
    n = len(next(iter(scores.values())))
    if len(y) != n:
        raise ValueError(f"{n} scores but {len(y)} labelled nodes in {data}")
    if "labels_sha256" in Z.files:
        h = hashlib.sha256(np.stack([y, step]).astype(np.int64).tobytes()).hexdigest()
        if h != str(Z["labels_sha256"]):
            raise ValueError("local Elliptic labels differ from the ones the scores were computed on")
    return scores, y, step
