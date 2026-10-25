"""
B-spline Kolmogorov-Arnold Network (KAN) for tabular blockchain features.

Implementation follows the "efficient" formulation (Liu et al. 2024, KAN;
Blealtan/efficient-kan): every edge (i -> j) carries

    phi_ij(x) = w_base_ij * silu(x) + w_spline_ij * sum_m c_ijm * B_m(x)

where B_m are B-spline basis functions of order k on a uniform grid with G
intervals over [grid_lo, grid_hi], extended by k knots on each side.

Design choices stated explicitly because they matter for the experiments:

1. Inputs are expected to be standardised (robust z-score + clipping is done
   by the caller). The grid covers [-grid_range, grid_range]; outside the
   extended grid all B-spline bases are zero, so phi_ij reduces to the SiLU
   base branch. K1 (HK.3) tests whether this extrapolation regime is
   reached under temporal distribution shift.
2. No grid refinement during training by default (update_grid is available but
   off), so that KAN and MLP get the same optimiser budget.
3. Regularisation: L1 on spline coefficients (sparsity, for interpretability)
   plus the usual weight decay in the optimiser.
4. `edge_functions()` returns phi_ij sampled on a dense grid for every edge of
   the first layer: this is what the interpretability analysis plots.
5. `to_lut()` samples every edge function on L points per grid interval and
   evaluates by linear interpolation (segment-wise LUT, as in LUT-KAN,
   Kuznetsov 2026, arXiv:2601.03332). Used only for inference-cost estimates.
"""

from __future__ import annotations

import math

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F


class KANLinear(nn.Module):
    def __init__(self, in_features: int, out_features: int, grid_size: int = 5,
                 spline_order: int = 3, grid_range: float = 3.0,
                 scale_noise: float = 0.1, base_activation=nn.SiLU):
        super().__init__()
        self.in_features = in_features
        self.out_features = out_features
        self.grid_size = grid_size
        self.spline_order = spline_order
        h = 2 * grid_range / grid_size
        grid = (torch.arange(-spline_order, grid_size + spline_order + 1, dtype=torch.float32) * h
                - grid_range)
        self.register_buffer("grid", grid.expand(in_features, -1).contiguous())
        self.base_weight = nn.Parameter(torch.empty(out_features, in_features))
        self.spline_weight = nn.Parameter(torch.empty(out_features, in_features, grid_size + spline_order))
        self.spline_scaler = nn.Parameter(torch.empty(out_features, in_features))
        self.base_activation = base_activation()
        self.scale_noise = scale_noise
        self.reset_parameters()

    def reset_parameters(self):
        nn.init.kaiming_uniform_(self.base_weight, a=math.sqrt(5))
        with torch.no_grad():
            noise = (torch.rand(self.out_features, self.in_features, self.grid_size + self.spline_order) - 0.5)
            self.spline_weight.copy_(noise * self.scale_noise / self.grid_size)
        nn.init.kaiming_uniform_(self.spline_scaler, a=math.sqrt(5))

    def b_splines(self, x: torch.Tensor) -> torch.Tensor:
        """x: (B, in) -> (B, in, grid_size + spline_order)"""
        grid = self.grid
        x = x.unsqueeze(-1)
        bases = ((x >= grid[:, :-1]) & (x < grid[:, 1:])).to(x.dtype)
        for k in range(1, self.spline_order + 1):
            bases = (
                (x - grid[:, : -(k + 1)]) / (grid[:, k:-1] - grid[:, : -(k + 1)]) * bases[:, :, :-1]
                + (grid[:, k + 1:] - x) / (grid[:, k + 1:] - grid[:, 1:(-k)]) * bases[:, :, 1:]
            )
        return bases.contiguous()

    @property
    def scaled_spline_weight(self):
        return self.spline_weight * self.spline_scaler.unsqueeze(-1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        base = F.linear(self.base_activation(x), self.base_weight)
        spl = F.linear(self.b_splines(x).view(x.size(0), -1),
                       self.scaled_spline_weight.view(self.out_features, -1))
        return base + spl

    def edge_values(self, x: torch.Tensor) -> torch.Tensor:
        """phi_ij(x_i) for every edge. x: (B, in) -> (B, out, in)."""
        base = self.base_activation(x).unsqueeze(1) * self.base_weight.unsqueeze(0)
        spl = torch.einsum("bim,oim->boi", self.b_splines(x), self.scaled_spline_weight)
        return base + spl

    def regularization_loss(self) -> torch.Tensor:
        return self.scaled_spline_weight.abs().mean()

    def fraction_outside_grid(self, x: torch.Tensor) -> float:
        lo = self.grid[0, self.spline_order].item()
        hi = self.grid[0, -self.spline_order - 1].item()
        return float(((x < lo) | (x > hi)).float().mean().item())


class KAN(nn.Module):
    def __init__(self, dims: list[int], grid_size: int = 5, spline_order: int = 3,
                 grid_range: float = 3.0):
        super().__init__()
        self.dims = list(dims)
        self.layers = nn.ModuleList([
            KANLinear(a, b, grid_size=grid_size, spline_order=spline_order, grid_range=grid_range)
            for a, b in zip(dims[:-1], dims[1:])
        ])

    def forward(self, x):
        for layer in self.layers:
            x = layer(x)
        return x

    def regularization_loss(self):
        return sum(l.regularization_loss() for l in self.layers)

    @torch.no_grad()
    def edge_functions(self, layer: int = 0, n_points: int = 201, x_range: float | None = None):
        """Sample phi_ij of one layer on a dense grid. Returns (xs, phi[out, in, n])."""
        L = self.layers[layer]
        r = x_range if x_range is not None else float(L.grid[0, -L.spline_order - 1])
        xs = torch.linspace(-r, r, n_points)
        X = xs.unsqueeze(1).expand(-1, L.in_features)
        phi = L.edge_values(X).permute(1, 2, 0).cpu().numpy()
        return xs.numpy(), phi

    @torch.no_grad()
    def input_relevance(self) -> np.ndarray:
        """Per-input relevance of the first layer: range of phi_ji summed over the hidden units j.

        Range (max - min) of each complete edge function (SiLU base term plus
        spline term, as in `edge_values`) over the grid, summed over the
        outgoing edges of input i (not averaged; with a fixed width the two
        differ by a constant factor). A function that is flat contributes
        nothing regardless of its weights.
        """
        _, phi = self.edge_functions(0)
        rng = phi.max(axis=2) - phi.min(axis=2)        # (out, in)
        return rng.sum(axis=0)

    def to_lut(self, points_per_interval: int = 8) -> "LUTKAN":
        return LUTKAN.from_kan(self, points_per_interval)


def count_parameters(model: nn.Module) -> int:
    return int(sum(p.numel() for p in model.parameters() if p.requires_grad))


def kan_param_count(dims, grid_size=5, spline_order=3) -> int:
    n = 0
    for a, b in zip(dims[:-1], dims[1:]):
        n += a * b * (grid_size + spline_order) + 2 * a * b
    return n


class LUTKAN:
    """NumPy inference-only KAN where every edge is a 1D lookup table.

    Each edge function is sampled at `points_per_interval * (G + 2k) + 1`
    equispaced points over the support of the extended knot vector and
    evaluated by linear interpolation; outside the support only the SiLU base
    branch is non-zero, which the LUT evaluates exactly.
    """

    def __init__(self, tables, lo, hi, base_weights):
        self.tables = tables            # list of (out, in, P) arrays
        self.lo = lo
        self.hi = hi
        self.base_weights = base_weights

    @classmethod
    @torch.no_grad()
    def from_kan(cls, kan: KAN, ppi: int = 8):
        tables, lo, hi, bws = [], [], [], []
        for L in kan.layers:
            # full support of the extended grid: outside it every B-spline is 0,
            # so the SiLU fallback below is exact, not an approximation
            a = float(L.grid[0, 0])
            b = float(L.grid[0, -1])
            P = ppi * (L.grid_size + 2 * L.spline_order) + 1
            xs = torch.linspace(a, b, P)
            X = xs.unsqueeze(1).expand(-1, L.in_features)
            phi = L.edge_values(X).permute(1, 2, 0).cpu().numpy().astype(np.float32)
            tables.append(phi)
            lo.append(a)
            hi.append(b)
            bws.append(L.base_weight.detach().cpu().numpy().astype(np.float32))
        return cls(tables, lo, hi, bws)

    def forward(self, x: np.ndarray) -> np.ndarray:
        x = np.asarray(x, dtype=np.float32)
        for T, a, b, bw in zip(self.tables, self.lo, self.hi, self.base_weights):
            out_f, in_f, P = T.shape
            inside = (x >= a) & (x <= b)
            pos = (np.clip(x, a, b) - a) / (b - a) * (P - 1)
            i0 = np.clip(np.floor(pos).astype(np.int64), 0, P - 2)
            w = (pos - i0.astype(np.float32))[:, None, :]          # stay in float32
            ar = np.arange(in_f)
            # gather T[:, i, i0[b, i]] -> (B, out, in)
            t0 = T[:, ar[None, :], i0].transpose(1, 0, 2)
            t1 = T[:, ar[None, :], i0 + 1].transpose(1, 0, 2)
            v = (1 - w) * t0 + w * t1
            silu = x / (1 + np.exp(-x))
            v_out = silu[:, None, :] * bw[None, :, :]
            v = np.where(inside[:, None, :], v, v_out)
            x = v.sum(axis=2)
        return x

    def nbytes(self) -> int:
        return int(sum(t.nbytes for t in self.tables) + sum(b.nbytes for b in self.base_weights))
