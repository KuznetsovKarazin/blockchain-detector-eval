import sys
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bal.models.kan import KAN, KANLinear, kan_param_count, count_parameters  # noqa: E402


def test_bspline_partition_of_unity_inside_grid():
    layer = KANLinear(3, 2, grid_size=5, spline_order=3, grid_range=3.0)
    x = torch.linspace(-2.99, 2.99, 101).unsqueeze(1).expand(-1, 3)
    B = layer.b_splines(x)
    assert torch.allclose(B.sum(-1), torch.ones_like(B.sum(-1)), atol=1e-5)


def test_bspline_vanishes_far_outside_grid():
    layer = KANLinear(1, 1, grid_size=5, spline_order=3, grid_range=3.0)
    x = torch.tensor([[10.0], [-10.0]])
    assert torch.all(layer.b_splines(x) == 0)


def test_edge_values_sum_to_forward():
    torch.manual_seed(0)
    layer = KANLinear(4, 3)
    x = torch.randn(16, 4)
    assert torch.allclose(layer.edge_values(x).sum(-1), layer(x), atol=1e-5)


def test_param_count_formula():
    m = KAN([10, 8, 1], grid_size=5)
    assert count_parameters(m) == kan_param_count([10, 8, 1], grid_size=5)


def test_lut_matches_float_model():
    torch.manual_seed(0)
    m = KAN([6, 4, 1], grid_size=5)
    x = (np.random.default_rng(0).normal(size=(256, 6)) * 3).astype(np.float32)   # includes out-of-grid inputs
    with torch.no_grad():
        y = m(torch.tensor(x)).numpy()
    lut = m.to_lut(points_per_interval=64)
    y2 = lut.forward(x)
    # out-of-support inputs use the exact SiLU branch; inside, the error is
    # linear-interpolation error only
    assert np.max(np.abs(y - y2)) < 5e-3


def test_lut_forward_stays_float32():
    import numpy as np
    import torch
    from bal.models.kan import KAN
    torch.manual_seed(0)
    lut = KAN([4, 3, 1], grid_size=5).to_lut(8)
    out = lut.forward(np.random.default_rng(0).normal(size=(16, 4)).astype(np.float32))
    assert out.dtype == np.float32
