"""GNN layers must not couple disconnected components (temporal isolation)."""

import numpy as np
import torch

from bal.models.gnn import GAT, GCN, SAGE, gat_edges, mean_adjacency, normalised_adjacency


def _two_components(n_extra=50, seed=0):
    rng = np.random.default_rng(seed)
    a = np.array([[0, 1, 2], [1, 2, 0]])                       # component A: nodes 0-2
    b = rng.integers(3, 3 + n_extra, size=(2, 4 * n_extra))      # component B: the rest
    return a, np.concatenate([a, b], axis=1), 3 + n_extra


def _check(model, build, scale=1.0):
    torch.manual_seed(0)
    a, ab, n = _two_components()
    X = torch.randn(n, 6) * scale
    model.eval()
    with torch.no_grad():
        out_a = model(X[:3], build(a, 3))
        out_ab = model(X, build(ab, n))[:3]
    assert torch.allclose(out_a, out_ab, atol=1e-6)
    # gradient of an A output w.r.t. any B feature is exactly zero
    Xg = X.clone().requires_grad_(True)
    model(Xg, build(ab, n))[0].backward()
    assert float(Xg.grad[3:].abs().max()) == 0.0


def test_gat_invariant_to_disconnected_component():
    torch.manual_seed(0)
    _check(GAT(6, 8, 2, 0.0), gat_edges, scale=10.0)   # large logits: the old global-max bug


def test_gcn_sage_invariant_to_disconnected_component():
    torch.manual_seed(0)
    _check(GCN(6, 8, 2, 0.0), normalised_adjacency)
    _check(SAGE(6, 8, 2, 0.0), mean_adjacency)
