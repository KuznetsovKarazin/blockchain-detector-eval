"""
K2  Clean inference-cost measurement for the Elliptic KAN (HK.4).

K1 timed the LUT while other experiments were running. This script trains
one KAN (width 8, grid 5, quantile inputs, seed 0 — the best matched
configuration of K1) and times, on an otherwise idle machine with one
thread, four inference paths on identical inputs:

    float_torch   KAN forward in PyTorch (B-spline basis evaluated each call)
    float_numpy   the same B-spline KAN re-implemented in NumPy (matched baseline)
    lut_numpy     LUTKAN (linear interpolation in sampled edge tables)
    mlp_torch     the parameter-matched MLP, for reference

Batch sizes 1, 32 and 1024; median of R repetitions after warm-up. Decision
agreement with the float model is reported for every LUT resolution.

The trained KAN and MLP (with their input transforms and the validation
threshold) are saved to models.pkl, so timing and agreement can be re-measured
on new inference code without retraining (--models <run>/models.pkl).

Usage
-----
    python scripts/k2_lut_latency.py --data data/raw/elliptic
    python scripts/k2_lut_latency.py --models results/kan/<run>/models.pkl
"""

from __future__ import annotations

import argparse
import os
import pickle
import sys
import time
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np          # noqa: E402
import pandas as pd         # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bal.data.elliptic import TEST_STEPS, TRAIN_STEPS, VAL_STEPS, load_elliptic  # noqa: E402
from bal.eval.metrics import threshold_at_val_f1                                # noqa: E402
from bal.models.kan import kan_param_count                                      # noqa: E402
from bal.models.tabular import TorchClassifier                                  # noqa: E402
from bal.utils.repro import dump_json, set_seed, write_manifest                 # noqa: E402

PPI = [4, 8, 16, 32]
BATCHES = [1, 32, 1024]


def numpy_kan(kan):
    """Float B-spline KAN in NumPy with the same maths as KANLinear.forward."""
    layers = []
    for L in kan.layers:
        layers.append((L.grid.detach().numpy().astype(np.float32),
                       L.base_weight.detach().numpy().astype(np.float32),
                       L.scaled_spline_weight.detach().numpy().astype(np.float32),
                       L.spline_order))

    def bsplines(x, grid, k):
        x = x[:, :, None]
        b = ((x >= grid[:, :-1]) & (x < grid[:, 1:])).astype(np.float32)
        for p in range(1, k + 1):
            b = ((x - grid[:, :-(p + 1)]) / (grid[:, p:-1] - grid[:, :-(p + 1)]) * b[:, :, :-1]
                 + (grid[:, p + 1:] - x) / (grid[:, p + 1:] - grid[:, 1:-p]) * b[:, :, 1:])
        return b

    def forward(x):
        x = np.asarray(x, dtype=np.float32)
        for grid, bw, sw, k in layers:
            base = (x / (1 + np.exp(-x))) @ bw.T
            B = bsplines(x, grid, k).reshape(len(x), -1)
            x = base + B @ sw.reshape(sw.shape[0], -1).T
        return x
    return forward


def _slim(clf):
    """Copy of a fitted classifier without cached training inputs (keeps models.pkl small)."""
    import copy
    c = copy.copy(clf)
    c.__dict__.pop("_raw_z", None)
    return c


def timeit(fn, x, reps):
    for _ in range(5):
        fn(x)
    ts = []
    for _ in range(reps):
        t0 = time.perf_counter()
        fn(x)
        ts.append(time.perf_counter() - t0)
    return float(np.median(ts) * 1e6)


def main():
    import torch
    torch.set_num_threads(1)
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/raw/elliptic")
    ap.add_argument("--out", default="results/kan")
    ap.add_argument("--reps", type=int, default=300)
    ap.add_argument("--models", default=None, help="models.pkl of an earlier run: skip training")
    a = ap.parse_args()
    run = Path(a.out) / time.strftime("k2_%Y%m%d_%H%M%S")
    run.mkdir(parents=True, exist_ok=True)
    d = load_elliptic(a.data)
    X, y = d.features("AF"), d.y
    tr, va = d.mask(TRAIN_STEPS), d.mask(VAL_STEPS)
    te = d.mask(TEST_STEPS)
    dim = X.shape[1]
    h = max(1, round((kan_param_count([dim, 8, 1], 5) - 1) / (dim + 2)))
    if a.models:
        with open(a.models, "rb") as f:
            saved = pickle.load(f)
        kan, mlp, thr = saved["kan"], saved["mlp"], saved["thr"]
    else:
        set_seed(0)
        kan = TorchClassifier("kan", hidden=(8,), grid=5, seed=0, prep="quantile").fit(X[tr], y[tr])
        mlp = TorchClassifier("mlp", hidden=(h,), seed=0, prep="quantile").fit(X[tr], y[tr])
        thr = threshold_at_val_f1(y[va], kan.predict_score(X[va]))
    with open(run / "models.pkl", "wb") as f:
        pickle.dump({"kan": _slim(kan), "mlp": _slim(mlp), "thr": thr}, f)
    logit_thr = float(np.log(thr / (1 - thr)))
    Z = kan._prep(X[te])
    Zm = mlp._prep(X[te])
    with torch.no_grad():
        ref = kan.net(torch.tensor(Z)).squeeze(-1).numpy()
    np_fwd = numpy_kan(kan.net)
    assert np.abs(np_fwd(Z[:2000]).squeeze(-1) - ref[:2000]).max() < 1e-3

    rows = []
    paths = {"float_torch": lambda z: kan.net(torch.tensor(z)),
             "float_numpy": np_fwd,
             "mlp_torch": None}
    luts = {ppi: kan.net.to_lut(ppi) for ppi in PPI}
    for B in BATCHES:
        zb, zmb = Z[:B], Zm[:B]
        with torch.no_grad():
            rows.append({"path": "float_torch", "batch": B, "us": timeit(paths["float_torch"], zb, a.reps)})
            rows.append({"path": "mlp_torch", "batch": B,
                         "us": timeit(lambda z: mlp.net(torch.tensor(z)), zmb, a.reps)})
        rows.append({"path": "float_numpy", "batch": B, "us": timeit(np_fwd, zb, a.reps)})
        for ppi, L in luts.items():
            rows.append({"path": f"lut_numpy_ppi{ppi}", "batch": B, "us": timeit(L.forward, zb, a.reps)})
        print(rows[-1], flush=True)
    lat = pd.DataFrame(rows)
    lat["us_per_tx"] = lat.us / lat.batch
    lat.to_csv(run / "latency.csv", index=False)

    acc = []
    for ppi, L in luts.items():
        lg = L.forward(Z).squeeze(-1)
        acc.append({"ppi": ppi, "bytes": L.nbytes(), "max_abs_logit_err": float(np.abs(lg - ref).max()),
                    "decision_agreement": float(((lg >= logit_thr) == (ref >= logit_thr)).mean()),
                    "n_disagree": int(((lg >= logit_thr) != (ref >= logit_thr)).sum()),
                    "lut_dtype": str(lg.dtype),
                    "n_test": int(len(ref))})
    acc = pd.DataFrame(acc)
    acc.to_csv(run / "lut_agreement.csv", index=False)
    info = {"kan_params": kan.n_params(), "mlp_params": mlp.n_params(), "mlp_hidden": h,
            "float_bytes": int(sum(p.numel() * 4 for p in kan.net.parameters())),
            "threads": 1, "reps": a.reps, "cpu": os.cpu_count()}
    dump_json(info, run / "info.json")
    print(lat.pivot(index="path", columns="batch", values="us_per_tx").round(2).to_string())
    print(acc.to_string())
    print(info)
    write_manifest(run, script=Path(__file__).name, config=vars(a),
                   data_files=[Path(a.data) / f for f in ("elliptic_txs_features.csv", "elliptic_txs_classes.csv")]
                   + ([a.models] if a.models else []))
    print("wrote", run)


if __name__ == "__main__":
    main()
