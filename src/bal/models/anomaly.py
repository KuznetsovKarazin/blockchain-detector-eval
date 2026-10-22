"""
Unsupervised / one-class detectors (bridge study B, KAN autoencoder in K).

All detectors follow `fit(X_train_normal)` / `score(X) -> higher = more anomalous`.
They never see attack labels. Feature scaling is part of each detector and is
fitted on the training data only.
"""

from __future__ import annotations

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import RobustScaler


class RobustZ:
    """Max absolute robust z-score over features (median / IQR scaling)."""

    name = "robust_z"

    def fit(self, X):
        self.sc = RobustScaler().fit(X)
        return self

    def score(self, X):
        return np.abs(self.sc.transform(X)).max(axis=1)


class ECOD:
    """Frozen, train-only ECDF tail score in the spirit of ECOD (Li et al. 2022).

    This is NOT the PyOD/paper algorithm: the empirical CDFs are fitted once on
    the training data and frozen (inductive scoring of a stream), they are
    smoothed as (rank + 1) / (n + 1), and the per-feature score is the
    two-sided -log min(left, right) without the paper's skewness-based choice
    of tail. Each per-feature score is therefore capped at log(n + 1).

    agg="sum"      sum over features (as in ECOD)
    agg="max"      largest per-feature tail score (ECOD-max): one extreme
                   feature is not diluted by many ordinary ones
    agg="max_lex"  ECOD-max with ties at the cap broken by the sum (score =
                   max + 1e-6 * sum); used so that an alarm budget can be met
                   without alarming on a whole tied block
    """

    name = "ecod"

    def __init__(self, agg: str = "sum"):
        self.agg = agg
        self.name = "ecod" if agg == "sum" else f"ecod_{agg}"
        if agg not in ("sum", "max", "max_lex"):
            raise ValueError(agg)

    def tail_scores(self, X):
        """(n, d) per-feature tail scores -log min(left, right)."""
        X = np.asarray(X, dtype=float)
        out = np.zeros(X.shape)
        for j in range(X.shape[1]):
            col = self.Xs[:, j]
            left = (np.searchsorted(col, X[:, j], side="right") + 1) / (self.n + 1)
            right = (self.n - np.searchsorted(col, X[:, j], side="left") + 1) / (self.n + 1)
            out[:, j] = -np.log(np.minimum(left, right))
        return out

    def fit(self, X):
        self.Xs = np.sort(np.asarray(X, dtype=float), axis=0)
        self.n = len(self.Xs)
        return self

    def score(self, X):
        t = self.tail_scores(X)
        if self.agg == "max":
            return t.max(axis=1)
        if self.agg == "max_lex":
            return t.max(axis=1) + 1e-6 * t.sum(axis=1)
        return t.sum(axis=1)


class IForest:
    name = "iforest"

    def __init__(self, seed: int = 0, n_estimators: int = 300):
        self.seed = seed
        self.n_estimators = n_estimators

    def fit(self, X):
        self.m = IsolationForest(n_estimators=self.n_estimators, random_state=self.seed,
                                 n_jobs=-1).fit(X)
        return self

    def score(self, X):
        return -self.m.score_samples(X)


class _TorchAE:
    """Autoencoder; reconstruction error is the anomaly score."""

    name = "ae"

    def __init__(self, kind: str = "mlp", hidden: int = 8, epochs: int = 60, lr: float = 1e-2,
                 seed: int = 0, batch: int = 256, kan_grid: int = 5):
        self.kind, self.hidden, self.epochs, self.lr = kind, hidden, epochs, lr
        self.seed, self.batch, self.kan_grid = seed, batch, kan_grid
        self.name = f"ae_{kind}"

    def _build(self, d):
        import torch.nn as nn
        if self.kind == "mlp":
            return nn.Sequential(nn.Linear(d, 2 * self.hidden), nn.SiLU(),
                                 nn.Linear(2 * self.hidden, self.hidden), nn.SiLU(),
                                 nn.Linear(self.hidden, 2 * self.hidden), nn.SiLU(),
                                 nn.Linear(2 * self.hidden, d))
        from bal.models.kan import KAN
        return KAN([d, self.hidden, d], grid_size=self.kan_grid)

    def fit(self, X):
        import torch
        torch.manual_seed(self.seed)
        torch.set_num_threads(1)
        self.sc = RobustScaler().fit(X)
        Z = np.clip(self.sc.transform(X), -5, 5) / 1.5
        Xt = torch.tensor(Z, dtype=torch.float32)
        self.net = self._build(Xt.shape[1])
        opt = torch.optim.AdamW(self.net.parameters(), lr=self.lr, weight_decay=1e-4)
        g = torch.Generator().manual_seed(self.seed)
        for _ in range(self.epochs):
            perm = torch.randperm(len(Xt), generator=g)
            for k in range(0, len(Xt), self.batch):
                xb = Xt[perm[k:k + self.batch]]
                loss = ((self.net(xb) - xb) ** 2).mean()
                opt.zero_grad()
                loss.backward()
                opt.step()
        return self

    def score(self, X):
        import torch
        Z = np.clip(self.sc.transform(X), -5, 5) / 1.5
        with torch.no_grad():
            Xt = torch.tensor(Z, dtype=torch.float32)
            return ((self.net(Xt) - Xt) ** 2).mean(dim=1).numpy()


def MLPAutoencoder(**kw):
    return _TorchAE(kind="mlp", **kw)


def KANAutoencoder(**kw):
    return _TorchAE(kind="kan", **kw)


DETECTORS = {
    "robust_z": lambda seed: RobustZ(),
    "ecod": lambda seed: ECOD(),
    "ecod_max": lambda seed: ECOD(agg="max"),
    "ecod_max_lex": lambda seed: ECOD(agg="max_lex"),
    "iforest": lambda seed: IForest(seed=seed),
    "ae_mlp": lambda seed: MLPAutoencoder(seed=seed),
    "ae_kan": lambda seed: KANAutoencoder(seed=seed),
}
