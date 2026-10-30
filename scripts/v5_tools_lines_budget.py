"""
V5  Static analysers at file and line level, and budget curves next to frozen models.

Inputs: a V4 run (raw tool results with lines) and a V3 run (per-file scores
of the frozen models). The mapping of tool rules to classes is fixed in
docs/PROTOCOLS.md (section V) and repeated in MAPPING below.

Outputs (results/contracts/<run>/):
* tool_file_level.csv   per tool, corpus and class: coverage, TP/FP/FN,
                        precision, recall, F1, end-to-end and analysed-only;
                        on the 50 original SolidiFI contracts the flag rate
* solidifi_located.csv  per tool and class on SolidiFI: file recall, located
                        recall (a mapped finding on a line of a snippet of the
                        class), snippet recall, mapped findings outside
                        snippets per positive file, flag rate on originals
* solidifi_templates.csv  snippet recall per tool and template
* budget_curves.parquet  expected precision / recall at every k for tools
                        (score = number of mapped findings), frozen models
                        and the hybrid (tool-flagged files first, by model)
* budget_points.csv     the curves at k = tool alarm count and k = 5, 10, 20,
                        with paired file-level bootstrap CIs of recall
                        differences against the tool
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from bal.data import solidifi                                  # noqa: E402
from bal.data.contracts import load_all                        # noqa: E402
from bal.utils.repro import atomic_to_csv, write_manifest      # noqa: E402
from c4_slither_vs_ml import at_budget                         # noqa: E402

MAPPING = {
    "slither": {"reentrancy": {"reentrancy-eth", "reentrancy-no-eth", "reentrancy-unlimited-gas",
                               "reentrancy-benign", "reentrancy-events"},
                "timestamp": {"timestamp"}, "unchecked": {"unchecked-lowlevel", "unchecked-send"},
                "tx_origin": {"tx-origin"}, "unchecked_merged": {"unchecked-lowlevel", "unchecked-send"}},
    "slither_full": None,             # same rules as slither, filled below
    "mythril": {"reentrancy": {"SWC-107"}, "arithmetic": {"SWC-101"}, "timestamp": {"SWC-116"},
                "unchecked": {"SWC-104"}, "tx_origin": {"SWC-115"}, "unprotected_send": {"SWC-105"},
                "unchecked_merged": {"SWC-104"}},
    "smartcheck": {"timestamp": {"SOLIDITY_EXACT_TIME"}, "unchecked": {"SOLIDITY_UNCHECKED_CALL"},
                   "tx_origin": {"SOLIDITY_TX_ORIGIN"}, "unchecked_merged": {"SOLIDITY_UNCHECKED_CALL"}},
}
MAPPING["slither_full"] = MAPPING["slither"]
CLASS_TYPES = {"reentrancy": ["Re-entrancy"], "timestamp": ["Timestamp-Dependency"],
               "unchecked": ["Unhandled-Exceptions"], "unprotected_send": ["Unchecked-Send"],
               "arithmetic": ["Overflow-Underflow"], "tx_origin": ["tx.origin"],
               "unchecked_merged": ["Unchecked-Send", "Unhandled-Exceptions"]}   # C2/C3 mapping, sensitivity only
KS = (5, 10, 20)


def load_v4(run: Path) -> pd.DataFrame:
    rows = []
    for p in sorted((run / "raw").glob("*/*.json")):
        d = json.loads(p.read_text())
        rows.append({"tool": d["tool"], "fid": d["fid"], "dataset": d["dataset"], "path": d["path"],
                     "status": d["status"], "findings": d.get("findings", [])})
    return pd.DataFrame(rows)


def mapped(findings, tool, cls):
    rules = MAPPING[tool].get(cls, set())
    return [f for f in findings if f["rule"] in rules]


def curve(y, s):
    """Expected precision and recall at every k (ties in expectation)."""
    out = []
    for k in range(1, len(y) + 1):
        p, r, _, _ = at_budget(y, s, k)
        out.append((k, p, r))
    return out


def recall_at(y, s, k):
    return at_budget(y, s, k)[1]


def paired_boot(y, s_a, s_b, k, n=2000, seed=0):
    """CI of recall@k(a) - recall@k(b), resampling files."""
    rng = np.random.default_rng(seed)
    d = []
    for _ in range(n):
        i = rng.integers(0, len(y), len(y))
        if y[i].sum() == 0:
            continue
        d.append(recall_at(y[i], s_a[i], k) - recall_at(y[i], s_b[i], k))
    return float(np.quantile(d, 0.025)), float(np.quantile(d, 0.975))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--v4-run", required=True, nargs="+", help="one or more V4 runs (tools are merged)")
    ap.add_argument("--v3-run", required=True)
    ap.add_argument("--out", default="results/contracts")
    a = ap.parse_args()
    run = Path(a.out) / time.strftime("v5_%Y%m%d_%H%M%S")
    run.mkdir(parents=True, exist_ok=True)
    R = pd.concat([load_v4(Path(r)) for r in a.v4_run], ignore_index=True)
    files, clean, cat = solidifi.load()
    sf = {str(f.path): f for f in files}
    df = load_all()
    lab = df.set_index("path")

    # ---------------- file level
    fl = []
    for (tool, ds), g in R.groupby(["tool", "dataset"]):
        ok = (g.status == "ok").to_numpy()
        for cls in CLASS_TYPES:
            if cls not in MAPPING[tool]:
                continue
            flag = np.array([len(mapped(f, tool, cls)) > 0 for f in g.findings])
            if ds == "solidifi_clean":
                fl.append({"tool": tool, "dataset": ds, "cls": cls, "scope": "end_to_end", "n": len(g),
                           "coverage": ok.mean(), "flag_rate": flag.mean(), "n_flagged": int(flag.sum())})
                continue
            if ds == "solidifi":
                y = np.array([sf[p].bug_type in CLASS_TYPES[cls] for p in g.path]).astype(int)
            elif cls in lab.columns:
                y = lab.loc[g.path, cls].to_numpy().astype(int)
            else:                                   # SolidiFI-only class
                continue
            if y.sum() == 0:
                continue
            for scope, m in (("end_to_end", np.ones(len(g), bool)), ("analysed_only", ok)):
                yy, ff = y[m], flag[m]
                tp, fp, fn = int((ff & (yy == 1)).sum()), int((ff & (yy == 0)).sum()), int((~ff & (yy == 1)).sum())
                fl.append({"tool": tool, "dataset": ds, "cls": cls, "scope": scope, "n": int(m.sum()),
                           "n_pos": int(yy.sum()), "coverage": ok.mean(), "pos_not_analysed": int((y[~ok] == 1).sum()),
                           "tp": tp, "fp": fp, "fn": fn, "precision": tp / max(1, tp + fp),
                           "recall": tp / max(1, tp + fn), "f1": 2 * tp / max(1, 2 * tp + fp + fn)})
    FL = pd.DataFrame(fl)
    atomic_to_csv(FL, run / "tool_file_level.csv", index=False)

    # ---------------- SolidiFI line level
    loc, per_t = [], []
    for tool, g in R[R.dataset == "solidifi"].groupby("tool"):
        gc = R[(R.dataset == "solidifi_clean") & (R.tool == tool)]
        for cls, types in CLASS_TYPES.items():
            if cls not in MAPPING[tool]:
                continue
            pos = g[[sf[p].bug_type in types for p in g.path]]
            file_hit, located, outside, snip_tot, snip_hit = [], [], [], 0, 0
            t_tot, t_hit = {}, {}
            for r in pos.itertuples():
                f = sf[r.path]
                fnd = mapped(r.findings, tool, cls)
                lines = {ln for x in fnd for ln in x["lines"]}
                inj = f.injected_lines()
                file_hit.append(bool(fnd))
                located.append(bool(lines & inj))
                outside.append(sum(1 for x in fnd if not (set(x["lines"]) & inj)))
                for s in f.snippets:
                    hit = bool(lines & set(range(s.line_start, s.line_end + 1)))
                    snip_tot += 1
                    snip_hit += hit
                    t_tot[s.template] = t_tot.get(s.template, 0) + 1
                    t_hit[s.template] = t_hit.get(s.template, 0) + hit
            n_ok = int((pos.status == "ok").sum())
            flag_clean = np.mean([bool(mapped(f, tool, cls)) for f in gc.findings]) if len(gc) else np.nan
            loc.append({"tool": tool, "cls": cls, "n_pos": len(pos), "n_pos_analysed": n_ok,
                        "file_recall": np.mean(file_hit), "located_recall": np.mean(located),
                        "snippet_recall": snip_hit / max(1, snip_tot), "n_snippets": snip_tot,
                        "findings_outside_per_file": np.mean(outside), "flag_rate_originals": flag_clean})
            for t in sorted(t_tot):
                per_t.append({"tool": tool, "cls": cls, "template": t, "n_snippets": t_tot[t],
                              "snippet_recall": t_hit[t] / t_tot[t]})
    atomic_to_csv(pd.DataFrame(loc), run / "solidifi_located.csv", index=False)
    atomic_to_csv(pd.DataFrame(per_t), run / "solidifi_templates.csv", index=False)

    # ---------------- budget curves (SmartBugs; annotated DAppSCAN with SmartCheck)
    v3 = Path(a.v3_run)
    sel = pd.read_csv(v3 / "v3_selection.csv")
    sc = pd.read_parquet(v3 / "target_scores.parquet")
    paths = df.path.to_numpy()
    curves, points = [], []
    for tgt, ds in (("smartbugs", "smartbugs"), ("dappscan", "dappscan")):
        for tool in MAPPING:
            g = R[(R.tool == tool) & (R.dataset == ds)]
            if g.empty:
                continue
            for cls in CLASS_TYPES:
                if cls not in MAPPING[tool]:
                    continue
                cnt = {p: float(len(mapped(f, tool, cls))) for p, f in zip(g.path, g.findings)}
                for r in sel[(sel.target == tgt) & (sel.cls == cls)].itertuples():
                    m = sc[(sc.cls == cls) & (sc.source == r.source) & (sc.target == tgt) & (sc.candidate == r.candidate)]
                    mm = m.groupby("file_id").agg(y=("y", "first"), s=("score", "mean")).reset_index()
                    mm["path"] = paths[mm.file_id]
                    mm = mm[mm.path.isin(cnt)]
                    y = mm.y.to_numpy().astype(int)
                    if y.sum() < 3:
                        continue
                    s_tool = mm.path.map(cnt).to_numpy()
                    s_model = mm.s.to_numpy().astype(float)
                    s_model01 = (s_model - s_model.min()) / max(1e-12, s_model.max() - s_model.min())
                    s_hyb = (s_tool > 0) * 2.0 + s_model01            # flagged files first, then by model
                    k_tool = int((s_tool > 0).sum())
                    for det, s in (("tool", s_tool), ("model", s_model), ("hybrid", s_hyb)):
                        for k, p, rr in curve(y, s):
                            curves.append({"target": tgt, "tool": tool, "cls": cls, "source": r.source,
                                           "model": r.candidate, "detector": det, "k": k, "precision": p, "recall": rr})
                    for k in sorted({k_tool, *KS}):
                        if k < 1 or k > len(y):
                            continue
                        row = {"target": tgt, "tool": tool, "cls": cls, "source": r.source, "model": r.candidate,
                               "k": k, "k_is_tool_alarms": k == k_tool, "n": len(y), "n_pos": int(y.sum())}
                        for det, s in (("tool", s_tool), ("model", s_model), ("hybrid", s_hyb)):
                            p, rr, _, _ = at_budget(y, s, k)
                            row[f"{det}_precision"], row[f"{det}_recall"] = p, rr
                        row["model_minus_tool_ci"] = "%.3f..%.3f" % paired_boot(y, s_model, s_tool, k)
                        row["hybrid_minus_tool_ci"] = "%.3f..%.3f" % paired_boot(y, s_hyb, s_tool, k)
                        points.append(row)
    pd.DataFrame(curves).to_parquet(run / "budget_curves.parquet", index=False)
    atomic_to_csv(pd.DataFrame(points), run / "budget_points.csv", index=False)
    print(FL.round(3).to_string())
    print(pd.DataFrame(loc).round(3).to_string())
    print(pd.DataFrame(points).round(3).to_string())
    write_manifest(run, script=Path(__file__).name, config=vars(a),
                   data_files=[*(Path(r) / "tool_runs.csv" for r in a.v4_run), v3 / "v3_selection.csv", v3 / "target_scores.parquet"],
                   extra={"mapping": {t: {c: sorted(v) for c, v in m.items()} for t, m in MAPPING.items()}})
    print("wrote", run)


if __name__ == "__main__":
    main()
