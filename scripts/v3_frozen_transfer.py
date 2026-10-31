"""
V3  Cross-corpus transfer with models frozen on source validation.

C2 reports the best transferred model chosen on the target itself. Here the
model is chosen before the target is touched:

1. Candidates (fixed list, in tie-break order): lex_raw / lex_norm with
   logistic regression, C in {0.1, 1, 10}; pat with RF, LightGBM and MLP
   (library settings of C2; RF, LightGBM and MLP with seeds 0-2).
2. Selection per (source, class): grouped 5-fold CV inside the source
   (SolidiFI: base contract; DAppSCAN: project), mean out-of-fold AUPRC over
   folds and seeds. A candidate within 0.005 of the best that comes earlier
   in the list wins.
3. Every candidate is refitted on the whole source and scored on every target
   (SmartBugs-curated; the 948 annotated DAppSCAN files; SolidiFI). The frozen
   model's target AUPRC gets a file-level bootstrap 95 % CI (2,000 resamples).
   The best candidate on the target (oracle) and the frozen candidate's rank
   among candidates on the target are exploratory.

Outputs: results/contracts/<run>/v3_cv.csv (source CV per candidate),
v3_selection.csv, v3_target.csv (every candidate on every target, frozen flag,
CI for the frozen one), target_scores.parquet (per-file scores of every
candidate and seed), manifest.json
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import average_precision_score
from sklearn.model_selection import GroupKFold

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bal.data.contracts import label_files, load_all                         # noqa: E402
from bal.eval.metrics import safe_ap                                          # noqa: E402
from bal.features.contract_features import normalised_text, pattern_matrix, raw_text  # noqa: E402
from bal.models.tabular import MODELS, logreg                                # noqa: E402
from bal.utils.repro import atomic_to_csv, set_seed, write_manifest           # noqa: E402

CLASSES = ["reentrancy", "arithmetic", "timestamp", "unchecked"]
CANDIDATES = ([(rep, "logreg", C) for rep in ("lex_raw", "lex_norm") for C in (0.1, 1.0, 10.0)]
              + [("pat", m, None) for m in ("rf", "lgbm", "mlp")])
STOCHASTIC = {"rf", "lgbm", "mlp"}
TIE = 0.005
PAIRS = [("solidifi", "smartbugs"), ("solidifi", "dappscan"), ("dappscan", "smartbugs"), ("dappscan", "solidifi")]


def name(c):
    rep, m, C = c
    return f"{rep}/{m}" + (f"/C={C:g}" if C is not None else "")


def fit_predict(c, seed, tr, te, df, P):
    rep, m, C = c
    set_seed(seed)
    if rep.startswith("lex"):
        col = "raw" if rep == "lex_raw" else "norm"
        v = TfidfVectorizer(token_pattern=r"\S+", ngram_range=(1, 3), min_df=2, max_features=50000,
                            sublinear_tf=True, lowercase=False)
        A = v.fit_transform(df[col].to_numpy()[tr])
        mdl = logreg(seed=seed, C=C).fit(A, df.y.to_numpy()[tr])
        return mdl.predict_score(v.transform(df[col].to_numpy()[te]))
    mdl = MODELS[m](seed=seed).fit(P[tr], df.y.to_numpy()[tr])
    return mdl.predict_score(P[te])


def boot_ci(y, s, n=2000, seed=0):
    rng = np.random.default_rng(seed)
    v = []
    for _ in range(n):
        i = rng.integers(0, len(y), len(y))
        if y[i].min() != y[i].max():
            v.append(average_precision_score(y[i], s[i]))
    return float(np.quantile(v, 0.025)), float(np.quantile(v, 0.975))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="results/contracts")
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--classes", default=",".join(CLASSES))
    ap.add_argument("--solidifi-unchecked", choices=["unhandled", "merged"], default="unhandled",
                    help="SolidiFI types labelled `unchecked`: Unhandled-Exceptions only, or also Unchecked-Send (C2)")
    a = ap.parse_args()
    run = Path(a.out) / time.strftime("v3_%Y%m%d_%H%M%S")
    run.mkdir(parents=True, exist_ok=True)

    df = load_all()
    if a.solidifi_unchecked == "unhandled":
        # SolidiFI "Unchecked-Send" injects unprotected Ether transfers (SWC-105), not unchecked return values
        df.loc[(df.dataset == "solidifi") & (df.sb_category == "Unchecked-Send"), "unchecked"] = 0
    df["norm"] = df.source.map(normalised_text)
    df["raw"] = df.source.map(raw_text)
    P = pattern_matrix(df.source).to_numpy(dtype=np.float32)
    idx = {"solidifi": np.flatnonzero(df.dataset == "solidifi"),
           "dappscan": np.flatnonzero(df.dataset == "dappscan"),
           "smartbugs": np.flatnonzero(df.dataset == "smartbugs")}
    target_idx = dict(idx, dappscan=np.flatnonzero((df.dataset == "dappscan") & (df.sb_category == "labelled")))

    cv_rows, tgt_rows, scores = [], [], []
    for cls in a.classes.split(","):
        df["y"] = df[cls].to_numpy()
        for src in ("solidifi", "dappscan"):
            S = idx[src]
            groups = df.group.to_numpy()[S]
            # 1. source CV
            for c in CANDIDATES:
                for seed in range(a.seeds if c[1] in STOCHASTIC else 1):
                    perm = {g: i for i, g in enumerate(np.random.default_rng(seed).permutation(np.unique(groups)))}
                    aps = []
                    for tr, te in GroupKFold(5).split(S, groups=[perm[g] for g in groups]):
                        s = fit_predict(c, seed, S[tr], S[te], df, P)
                        aps.append(safe_ap(df.y.to_numpy()[S[te]], s))
                    cv_rows.append({"cls": cls, "source": src, "candidate": name(c), "seed": seed,
                                    "cv_auprc": float(np.nanmean(aps)), "cv_auprc_folds": ";".join(f"{x:.4f}" for x in aps)})
                    print(cv_rows[-1], flush=True)
            cv = pd.DataFrame(cv_rows)
            cv = cv[(cv.cls == cls) & (cv.source == src)].groupby("candidate", sort=False).cv_auprc.mean()
            best = cv.max()
            frozen = next(name(c) for c in CANDIDATES if cv[name(c)] >= best - TIE)
            # 2. refit on the whole source, score every target
            for c in CANDIDATES:
                for seed in range(a.seeds if c[1] in STOCHASTIC else 1):
                    for (s_, tgt) in PAIRS:
                        if s_ != src:
                            continue
                        T = target_idx[tgt]
                        yt = df.y.to_numpy()[T]
                        if yt.sum() < 3:
                            continue
                        s = fit_predict(c, seed, S, T, df, P)
                        scores.append(pd.DataFrame({"cls": cls, "source": src, "target": tgt, "candidate": name(c),
                                                    "seed": seed, "file_id": T, "y": yt, "score": s.astype(np.float32)}))
                        tgt_rows.append({"cls": cls, "source": src, "target": tgt, "candidate": name(c), "seed": seed,
                                         "auprc": safe_ap(yt, s), "base_rate": float(yt.mean()), "n": len(yt),
                                         "n_pos": int(yt.sum()), "cv_auprc": float(cv[name(c)]),
                                         "frozen": name(c) == frozen})
            print(cls, src, "frozen:", frozen, "cv:", cv.round(3).to_dict(), flush=True)

    cvdf = pd.DataFrame(cv_rows)
    atomic_to_csv(cvdf, run / "v3_cv.csv", index=False)
    T = pd.DataFrame(tgt_rows)
    sc = pd.concat(scores)
    sc.to_parquet(run / "target_scores.parquet", index=False)
    # seed-mean per candidate; CI for the frozen candidate from seed-mean scores
    agg = T.groupby(["cls", "source", "target", "candidate"], sort=False).agg(
        auprc=("auprc", "mean"), base_rate=("base_rate", "first"), n=("n", "first"), n_pos=("n_pos", "first"),
        cv_auprc=("cv_auprc", "first"), frozen=("frozen", "first")).reset_index()
    agg["rank_on_target"] = agg.groupby(["cls", "source", "target"]).auprc.rank(ascending=False, method="min")
    lo, hi = [], []
    for r in agg.itertuples():
        if not r.frozen:
            lo.append(np.nan), hi.append(np.nan)
            continue
        m = sc[(sc.cls == r.cls) & (sc.source == r.source) & (sc.target == r.target) & (sc.candidate == r.candidate)]
        mm = m.groupby("file_id").agg(y=("y", "first"), s=("score", "mean"))
        l_, h_ = boot_ci(mm.y.to_numpy(), mm.s.to_numpy())
        lo.append(l_), hi.append(h_)
    agg["ci_lo"], agg["ci_hi"] = lo, hi
    atomic_to_csv(agg, run / "v3_target.csv", index=False)
    sel = agg[agg.frozen].merge(
        agg.loc[agg.groupby(["cls", "source", "target"]).auprc.idxmax(), ["cls", "source", "target", "candidate", "auprc"]]
           .rename(columns={"candidate": "oracle", "auprc": "oracle_auprc"}), on=["cls", "source", "target"])
    atomic_to_csv(sel, run / "v3_selection.csv", index=False)
    print(sel.round(3).to_string())
    write_manifest(run, script=Path(__file__).name, config=vars(a),
                   data_sets={f"sources_{ds}": g.path for ds, g in df.groupby("dataset")} | {"label_files": label_files()},
                   extra={"candidates": [name(c) for c in CANDIDATES], "tie": TIE, "pairs": PAIRS})
    print("wrote", run)


if __name__ == "__main__":
    main()
