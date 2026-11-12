"""V7b  Agreement between the template reading and other readers (amendment 6).

Reads the three-level reading of the 44 templates (data/audit/template_three_levels.csv),
the item key of the blinded form (results/contracts/v7_rater_form/key.csv) and any
number of filled forms (xlsx as sent, or csv with columns Item, Q1..., Q2..., Q3...).
Reports, per question (operation / weakness / exploit), pairwise Cohen's kappa and
raw agreement, Fleiss' kappa over all readers, and per reader and SolidiFI type the
share of injected snippets read as `no` (and as not `yes`).

    python scripts/v7b_reader_agreement.py --forms <dir> --label llm_readers
"""
from __future__ import annotations

import argparse
import warnings
import itertools
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import cohen_kappa_score

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from bal.utils.repro import atomic_to_csv, write_manifest   # noqa: E402

LEVELS = Path("data/audit/template_three_levels.csv")
KEY = Path("results/contracts/v7_rater_form/key.csv")
QS = {"operation": "Q1", "weakness": "Q2", "exploit": "Q3"}
NORM = {"unclear": "unsure"}


def read_form(p: Path) -> pd.DataFrame:
    if p.suffix == ".xlsx":
        import openpyxl
        ws = openpyxl.load_workbook(p, data_only=True)["Items"]
        rows = list(ws.iter_rows(values_only=True))
        h = next(i for i, r in enumerate(rows) if r and r[0] == "Item")
        d = pd.DataFrame(rows[h + 1:], columns=rows[h])
    else:
        d = pd.read_csv(p)
    out = {"item": d["Item"].astype(str).str.strip()}
    for q, prefix in QS.items():
        col = next(c for c in d.columns if isinstance(c, str) and c.startswith(prefix))
        out[q] = d[col].astype(str).str.strip().str.lower().replace(NORM)
    return pd.DataFrame(out)[lambda x: x.item.str.match(r"Q\d\d$")]


def fleiss(table: pd.DataFrame) -> float:
    """Fleiss' kappa; rows = items, columns = readers."""
    cats = sorted(set(table.to_numpy().ravel()))
    n = table.shape[1]
    counts = np.stack([(table == c).sum(axis=1).to_numpy() for c in cats], axis=1)
    p_i = ((counts * (counts - 1)).sum(axis=1)) / (n * (n - 1))
    p_j = counts.sum(axis=0) / counts.sum()
    pe = (p_j ** 2).sum()
    return float((p_i.mean() - pe) / (1 - pe)) if pe < 1 else float("nan")


def main() -> None:
    warnings.filterwarnings("ignore")
    ap = argparse.ArgumentParser()
    ap.add_argument("--forms", required=True, help="folder with filled forms (xlsx/csv)")
    ap.add_argument("--label", required=True)
    ap.add_argument("--out", default="results/contracts")
    a = ap.parse_args()
    run = Path(a.out) / time.strftime(f"v7b_{a.label}_%Y%m%d_%H%M%S")
    run.mkdir(parents=True, exist_ok=True)

    base = pd.read_csv(KEY).merge(pd.read_csv(LEVELS), on="template")
    readers = {"authors": base[["item", *QS]].copy()}
    for p in sorted(Path(a.forms).glob("*")):
        if p.suffix in (".xlsx", ".csv"):
            readers[p.stem] = read_form(p)
    wide = {q: base[["item", "template", "bug_type", "occurrences"]].copy() for q in QS}
    for name, d in readers.items():
        for q in QS:
            wide[q] = wide[q].merge(d[["item", q]].rename(columns={q: name}), on="item")
    names = list(readers)
    pair, share = [], []
    for q, w in wide.items():
        for x, y in itertools.combinations(names, 2):
            pair.append({"question": q, "a": x, "b": y, "kappa": cohen_kappa_score(w[x], w[y]),
                         "agreement": float((w[x] == w[y]).mean())})
        pair.append({"question": q, "a": "all", "b": "all", "kappa": fleiss(w[names]), "agreement": np.nan})
        for t, g in w.groupby("bug_type"):
            o = g.occurrences.sum()
            for r in names:
                share.append({"question": q, "bug_type": t, "reader": r,
                              "share_no": g.occurrences[g[r] == "no"].sum() / o,
                              "share_not_yes": g.occurrences[g[r] != "yes"].sum() / o})
    P, S = pd.DataFrame(pair), pd.DataFrame(share)
    atomic_to_csv(P, run / "agreement.csv", index=False)
    atomic_to_csv(S, run / "shares.csv", index=False)
    for q, w in wide.items():
        atomic_to_csv(w, run / f"answers_{q}.csv", index=False)
    pd.set_option("display.width", 200)
    print(P.round(2).to_string())
    print(S.pivot_table(index=["question", "bug_type"], columns="reader", values="share_no").round(2).to_string())
    write_manifest(run, script=Path(__file__).name, config=vars(a),
                   data_files=[LEVELS, KEY, *[p for p in sorted(Path(a.forms).glob("*")) if p.suffix in (".xlsx", ".csv")]])
    print(f"wrote {run}")


if __name__ == "__main__":
    main()
