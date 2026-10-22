"""T1 aggregation must be idempotent and must not read its own outputs."""

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

_p = Path(__file__).resolve().parents[1] / "scripts" / "t1_temporal_benchmark.py"
_spec = importlib.util.spec_from_file_location("t1", _p)
t1 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(t1)


def _part(run, tag, model):
    p = run / "parts" / tag
    p.mkdir(parents=True)
    pd.DataFrame([{"model": model, "features": "AF", "seed": s, "val_auprc": 0.5 + s / 10, "test_f1": 0.4,
                   "test_auprc": 0.3, "pre_f1": 0.5, "post_f1": 0.1} for s in range(2)]).to_csv(p / "metrics.csv", index=False)
    pd.DataFrame([{"model": model, "features": "AF", "seed": 0, "step": 35, "f1": 0.4}]).to_csv(p / "per_step_f1.csv", index=False)
    np.savez_compressed(p / "scores.npz", **{f"{model}|AF|0": np.zeros(3, np.float32)})


def test_aggregate_twice_gives_identical_files(tmp_path):
    _part(tmp_path, "a", "rf")
    _part(tmp_path, "b", "mlp")
    t1.aggregate(tmp_path)
    first = {f: (tmp_path / f).read_bytes() for f in ("metrics.csv", "metrics_summary.csv", "headline_by_validation.csv")}
    t1.aggregate(tmp_path)
    assert first == {f: (tmp_path / f).read_bytes() for f in first}
    assert len(pd.read_csv(tmp_path / "metrics.csv")) == 4
