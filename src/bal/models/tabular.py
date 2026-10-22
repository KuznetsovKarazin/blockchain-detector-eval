"""
Supervised classifiers with a common interface: fit(X, y) / predict_score(X).

Neural models (MLP, KAN) share the same training loop, optimiser, early
stopping rule and budget ("matched protocol", K). The only other difference is
the input: after the shared fitted transform, the KAN input is multiplied by
0.6 so that it stays inside the spline grid. Tree models use library defaults plus class
weighting; no per-split tuning is done on test data.
"""

from __future__ import annotations

import os

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler


class SkWrap:
    def __init__(self, est, scale: bool = False, name: str = ""):
        self.est = est
        self.scale = scale
        self.name = name

    def fit(self, X, y):
        if self.scale:
            self.sc = StandardScaler(with_mean=not _is_sparse(X)).fit(X)
            X = self.sc.transform(X)
        self.est.fit(X, y)
        return self

    def predict_score(self, X):
        if self.scale:
            X = self.sc.transform(X)
        return self.est.predict_proba(X)[:, 1]


def _is_sparse(X):
    return hasattr(X, "tocsr")


def _n_jobs() -> int:
    """Worker threads for tree models; BAL_N_JOBS lets parallel runs share the CPU."""
    return int(os.environ.get("BAL_N_JOBS", "4"))


def logreg(seed=0, C=1.0):
    return SkWrap(LogisticRegression(C=C, max_iter=3000, class_weight="balanced", random_state=seed),
                  scale=True, name="logreg")


def random_forest(seed=0, n=500):
    return SkWrap(RandomForestClassifier(n_estimators=n, class_weight="balanced_subsample",
                                         min_samples_leaf=1, n_jobs=_n_jobs(), random_state=seed), name="rf")


def lightgbm(seed=0):
    import lightgbm as lgb
    return SkWrap(lgb.LGBMClassifier(n_estimators=400, learning_rate=0.05, num_leaves=31,
                                     subsample=0.8, subsample_freq=1, colsample_bytree=0.8,
                                     class_weight="balanced", random_state=seed, verbose=-1,
                                     n_jobs=_n_jobs()), name="lgbm")


class TorchClassifier:
    """MLP or KAN binary classifier with a fixed, shared training protocol.

    * inputs: robust-scaled, clipped to [-clip, clip] then divided by clip/grid_range
      so that the KAN grid [-3, 3] covers the bulk of the data;
    * loss: BCE with positive-class weight = n_neg / n_pos (capped);
    * optimiser: AdamW, lr 3e-3, weight decay 1e-4, batch 512;
    * early stopping on a stratified 15% validation split (AUPRC), patience 15.
    """

    def __init__(self, kind="mlp", hidden=(32, 16), grid=5, seed=0, epochs=200, lr=3e-3,
                 batch=512, patience=15, l1_spline=0.0, clip=5.0, name=None, verbose=False,
                 threads=1, prep="robust", weight_decay=1e-4):
        self.kind, self.hidden, self.grid, self.seed = kind, tuple(hidden), grid, seed
        self.epochs, self.lr, self.batch, self.patience = epochs, lr, batch, patience
        self.l1_spline, self.clip, self.verbose = l1_spline, clip, verbose
        self.threads = threads   # small nets: 1 thread is faster than 4 and deterministic
        self.prep, self.weight_decay = prep, weight_decay
        self.name = name or kind

    def _build(self, d):
        import torch.nn as nn
        if self.kind == "mlp":
            layers, prev = [], d
            for h in self.hidden:
                layers += [nn.Linear(prev, h), nn.SiLU()]
                prev = h
            layers.append(nn.Linear(prev, 1))
            return nn.Sequential(*layers)
        from bal.models.kan import KAN
        return KAN([d, *self.hidden, 1], grid_size=self.grid)

    def _prep(self, X, fit=False):
        from sklearn.preprocessing import QuantileTransformer, RobustScaler
        X = np.asarray(X, dtype=np.float32)
        if fit:
            if self.prep == "quantile":
                # marginal ranks -> N(0, 1); test values beyond the training range
                # map to the extreme training quantile instead of leaving the grid
                self.sc = QuantileTransformer(n_quantiles=1000, output_distribution="normal",
                                              subsample=200_000, random_state=self.seed).fit(X)
            else:
                self.sc = RobustScaler(quantile_range=(10, 90)).fit(X)
        Z = self.sc.transform(X).astype(np.float32)
        if self.prep == "quantile":
            Z = Z * (self.clip / 3.0)     # +-3 sd -> +-clip, so the KAN grid covers 99.7% of training mass
        Z = np.nan_to_num(Z, nan=0.0, posinf=self.clip, neginf=-self.clip)
        self._raw_z = Z
        return np.clip(Z, -self.clip, self.clip) * (3.0 / self.clip) if self.kind == "kan" else np.clip(Z, -self.clip, self.clip)

    def fit(self, X, y):
        import torch
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import average_precision_score
        torch.manual_seed(self.seed)
        torch.set_num_threads(self.threads)
        y = np.asarray(y).astype(np.float32)
        Z = self._prep(X, fit=True)
        strat = y if y.sum() >= 2 else None
        tr, va = train_test_split(np.arange(len(y)), test_size=0.15, random_state=self.seed, stratify=strat)
        Xt, yt = torch.tensor(Z[tr]), torch.tensor(y[tr])
        Xv, yv = torch.tensor(Z[va]), y[va]
        self.net = self._build(Z.shape[1])
        pw = float(min(100.0, max(1.0, (len(yt) - yt.sum().item()) / max(1.0, yt.sum().item()))))
        lossf = torch.nn.BCEWithLogitsLoss(pos_weight=torch.tensor(pw))
        opt = torch.optim.AdamW(self.net.parameters(), lr=self.lr, weight_decay=self.weight_decay)
        g = torch.Generator().manual_seed(self.seed)
        best, best_state, bad = -1.0, None, 0
        for ep in range(self.epochs):
            self.net.train()
            perm = torch.randperm(len(Xt), generator=g)
            for k in range(0, len(Xt), self.batch):
                idx = perm[k:k + self.batch]
                logit = self.net(Xt[idx]).squeeze(-1)
                loss = lossf(logit, yt[idx])
                if self.kind == "kan" and self.l1_spline > 0:
                    loss = loss + self.l1_spline * self.net.regularization_loss()
                opt.zero_grad()
                loss.backward()
                opt.step()
            self.net.eval()
            with torch.no_grad():
                sv = self.net(Xv).squeeze(-1).numpy()
            score = average_precision_score(yv, sv) if yv.sum() > 0 else -float(lossf(torch.tensor(sv), torch.tensor(yv)))
            if score > best + 1e-4:
                best, bad = score, 0
                best_state = {k: v.clone() for k, v in self.net.state_dict().items()}
            else:
                bad += 1
                if bad >= self.patience:
                    break
        if best_state is not None:
            self.net.load_state_dict(best_state)
        self.epochs_run = ep + 1
        self.val_auprc = best
        return self

    def predict_score(self, X, chunk: int = 8192):
        import torch
        Z = self._prep(X)
        out = np.empty(len(Z), dtype=np.float32)
        self.net.eval()
        with torch.no_grad():       # chunked: a KAN's B-spline basis is (batch, d, G+k)
            for k in range(0, len(Z), chunk):
                out[k:k + chunk] = torch.sigmoid(self.net(torch.tensor(Z[k:k + chunk])).squeeze(-1)).numpy()
        return out

    def n_params(self):
        from bal.models.kan import count_parameters
        return count_parameters(self.net)


def mlp(seed=0, hidden=(32, 16), **kw):
    return TorchClassifier("mlp", hidden=hidden, seed=seed, name="mlp", **kw)


def kan(seed=0, hidden=(8,), grid=5, **kw):
    return TorchClassifier("kan", hidden=hidden, grid=grid, seed=seed, name="kan", **kw)


MODELS = {"logreg": logreg, "rf": random_forest, "lgbm": lightgbm, "mlp": mlp, "kan": kan}
