"""
Graph neural networks in plain PyTorch (no torch_geometric dependency), for
Elliptic-style node classification.

* GCN (Kipf & Welling 2017): symmetric-normalised adjacency with self loops.
* GraphSAGE-mean (Hamilton et al. 2017): concat(self, mean of neighbours).
* GAT (Velickovic et al. 2018): single-head additive attention over neighbours.

The graph is treated as undirected. Training uses the full graph (all time
steps) but the loss only on training-step labelled nodes; since Elliptic edges
never cross time steps, validation/test nodes are in components disconnected
from training nodes (see bal.data.elliptic).

`neighbour_features` builds the cheap alternative a strong tabular model can
use instead: mean / max of neighbours' features and the degree.
"""

from __future__ import annotations

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F


def _undirected(edges: np.ndarray, n: int):
    e = np.concatenate([edges, edges[::-1]], axis=1)
    e = np.unique(e, axis=1)
    return torch.tensor(e, dtype=torch.long)


def normalised_adjacency(edges: np.ndarray, n: int) -> torch.Tensor:
    e = _undirected(edges, n)
    loops = torch.arange(n).repeat(2, 1)
    e = torch.cat([e, loops], dim=1)
    deg = torch.zeros(n).scatter_add_(0, e[0], torch.ones(e.shape[1]))
    w = deg[e[0]].rsqrt() * deg[e[1]].rsqrt()
    return torch.sparse_coo_tensor(e, w, (n, n)).coalesce()


def mean_adjacency(edges: np.ndarray, n: int) -> torch.Tensor:
    e = _undirected(edges, n)
    deg = torch.zeros(n).scatter_add_(0, e[0], torch.ones(e.shape[1])).clamp(min=1)
    w = 1.0 / deg[e[0]]
    return torch.sparse_coo_tensor(e, w, (n, n)).coalesce()


class GCN(nn.Module):
    def __init__(self, d_in, hidden=64, layers=2, dropout=0.3):
        super().__init__()
        dims = [d_in] + [hidden] * layers
        self.lins = nn.ModuleList([nn.Linear(a, b) for a, b in zip(dims[:-1], dims[1:])])
        self.out = nn.Linear(hidden, 1)
        self.dropout = dropout

    def forward(self, x, A):
        for lin in self.lins:
            x = torch.sparse.mm(A, lin(x))
            x = F.dropout(F.relu(x), self.dropout, self.training)
        return self.out(x).squeeze(-1)


class SAGE(nn.Module):
    def __init__(self, d_in, hidden=64, layers=2, dropout=0.3):
        super().__init__()
        dims = [d_in] + [hidden] * layers
        self.self_l = nn.ModuleList([nn.Linear(a, b) for a, b in zip(dims[:-1], dims[1:])])
        self.nei_l = nn.ModuleList([nn.Linear(a, b, bias=False) for a, b in zip(dims[:-1], dims[1:])])
        self.out = nn.Linear(hidden, 1)
        self.dropout = dropout

    def embed(self, x, A):
        for ls, ln in zip(self.self_l, self.nei_l):
            x = ls(x) + ln(torch.sparse.mm(A, x))
            x = F.dropout(F.relu(x), self.dropout, self.training)
        return x

    def forward(self, x, A):
        return self.out(self.embed(x, A)).squeeze(-1)


class GAT(nn.Module):
    """Single-head GAT layer stack using an edge list (memory O(E))."""

    def __init__(self, d_in, hidden=64, layers=2, dropout=0.3):
        super().__init__()
        dims = [d_in] + [hidden] * layers
        self.lins = nn.ModuleList([nn.Linear(a, b, bias=False) for a, b in zip(dims[:-1], dims[1:])])
        self.att_src = nn.ParameterList([nn.Parameter(torch.randn(b) * 0.1) for b in dims[1:]])
        self.att_dst = nn.ParameterList([nn.Parameter(torch.randn(b) * 0.1) for b in dims[1:]])
        self.out = nn.Linear(hidden, 1)
        self.dropout = dropout

    def forward(self, x, E):
        n = x.shape[0]
        src, dst = E
        for lin, a_s, a_d in zip(self.lins, self.att_src, self.att_dst):
            h = lin(x)
            logits = F.leaky_relu((h[src] * a_s).sum(-1) + (h[dst] * a_d).sum(-1), 0.2)
            # softmax over the in-edges of each destination, stabilised by the
            # per-destination maximum (a global maximum couples disconnected
            # components once the denominator clamp is hit)
            m = torch.full((n,), -torch.inf).scatter_reduce(0, dst, logits, "amax", include_self=True)
            w = (logits - m[dst]).exp()
            denom = torch.zeros(n).index_add_(0, dst, w)
            alpha = w / denom[dst]
            agg = torch.zeros_like(h).index_add_(0, dst, h[src] * alpha.unsqueeze(-1))
            x = F.dropout(F.elu(agg), self.dropout, self.training)
        return self.out(x).squeeze(-1)


def gat_edges(edges: np.ndarray, n: int) -> torch.Tensor:
    e = _undirected(edges, n)
    loops = torch.arange(n).repeat(2, 1)
    return torch.cat([e, loops], dim=1)


class GraphClassifier:
    """Full-batch training with early stopping on validation AUPRC."""

    def __init__(self, kind="sage", hidden=64, layers=2, dropout=0.3, lr=1e-2, epochs=300,
                 patience=30, seed=0, threads=4):
        self.kind, self.hidden, self.layers, self.dropout = kind, hidden, layers, dropout
        self.lr, self.epochs, self.patience, self.seed, self.threads = lr, epochs, patience, seed, threads
        self.name = kind

    def fit(self, X, edges, y, train_mask, val_mask):
        from sklearn.metrics import average_precision_score
        from sklearn.preprocessing import StandardScaler
        torch.manual_seed(self.seed)
        torch.set_num_threads(self.threads)
        n = X.shape[0]
        sc = StandardScaler().fit(X[train_mask])
        Xt = torch.tensor(np.clip(sc.transform(X), -10, 10), dtype=torch.float32)
        if self.kind == "gcn":
            G = normalised_adjacency(edges, n)
            net = GCN(X.shape[1], self.hidden, self.layers, self.dropout)
        elif self.kind == "sage":
            G = mean_adjacency(edges, n)
            net = SAGE(X.shape[1], self.hidden, self.layers, self.dropout)
        elif self.kind == "gat":
            G = gat_edges(edges, n)
            net = GAT(X.shape[1], self.hidden, self.layers, self.dropout)
        else:
            raise ValueError(self.kind)
        yt = torch.tensor(np.clip(y, 0, 1), dtype=torch.float32)
        tr = torch.tensor(np.where(train_mask)[0])
        va = np.where(val_mask)[0]
        pos = yt[tr].sum().item()
        lossf = nn.BCEWithLogitsLoss(pos_weight=torch.tensor((len(tr) - pos) / max(pos, 1)))
        opt = torch.optim.AdamW(net.parameters(), lr=self.lr, weight_decay=5e-4)
        best, state, bad = -1, None, 0
        for ep in range(self.epochs):
            net.train()
            out = net(Xt, G)
            loss = lossf(out[tr], yt[tr])
            opt.zero_grad()
            loss.backward()
            opt.step()
            net.eval()
            with torch.no_grad():
                s = net(Xt, G).numpy()
            ap = average_precision_score(y[va], s[va])
            if ap > best + 1e-4:
                best, bad = ap, 0
                state = {k: v.clone() for k, v in net.state_dict().items()}
            else:
                bad += 1
                if bad >= self.patience:
                    break
        net.load_state_dict(state)
        net.eval()
        with torch.no_grad():
            self.scores_ = torch.sigmoid(net(Xt, G)).numpy()
        self.val_auprc, self.epochs_run, self.net, self._G, self._Xt = best, ep + 1, net, G, Xt
        return self

    def embeddings(self):
        if self.kind != "sage":
            raise ValueError("embeddings only for sage")
        with torch.no_grad():
            return self.net.embed(self._Xt, self._G).numpy()


def neighbour_features(X: np.ndarray, edges: np.ndarray) -> np.ndarray:
    """[mean of neighbours, max of neighbours, log1p(degree)] for every node."""
    n = X.shape[0]
    e = _undirected(edges, n).numpy()
    src, dst = e
    deg = np.bincount(dst, minlength=n).astype(np.float32)
    s = np.zeros_like(X)
    np.add.at(s, dst, X[src])
    mean = s / np.maximum(deg, 1)[:, None]
    mx = np.full_like(X, -np.inf)
    np.maximum.at(mx, dst, X[src])
    mx[~np.isfinite(mx)] = 0
    return np.hstack([mean, mx, np.log1p(deg)[:, None]]).astype(np.float32)
