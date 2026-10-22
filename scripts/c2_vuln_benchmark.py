"""
C2  How much reported accuracy survives leakage control and a change of
labelling regime?

Research question
-----------------
Learning-based detectors are usually evaluated with random file-level splits
inside one corpus. We measure, per vulnerability class:

HC.1  Random vs group split: AUPRC under a random split is higher than under a
       split by base contract / project with near-duplicates merged (leakage).
HC.2  Identifier artefacts: on SolidiFI, a lexical model on RAW tokens is
       near-perfect; normalising identifiers removes much of that advantage.
HC.3  Regime transfer: models trained on INJECTED (SolidiFI) or AUDIT
       (DAppSCAN) labels lose most of their in-corpus AUPRC on the MANUAL labels
       of SmartBugs-curated.
HC.4  Interpretable pattern features + small models (LGBM, KAN) transfer
       better than lexical models.

Representations: raw-token TF-IDF (lex_raw), normalised-token TF-IDF
(lex_norm), expert-pattern counts (pat).
Models: logistic regression on lex_*, RF / LightGBM / MLP / KAN on pat.

Protocols (within one corpus, 5 folds, out-of-fold scores)
---------------------------------------------------------
random          stratified 5-fold over files
random_matched  same folds, each training fold sub-sampled (stratified) to the
                training size of the matching `safe` fold: separates the effect
                of removing overlap from the effect of a smaller training set
project         GroupKFold by declared group (SolidiFI base contract, DAppSCAN
                project, SmartBugs file); near-duplicates may cross folds
safe            GroupKFold by declared group merged with near-duplicate
                components (Jaccard >= 0.8, exact duplicates always merged).
                On DAppSCAN shared library code chains most projects into one
                group (fold sizes are written to folds.csv)
local_random /  files whose near-duplicate component stays inside one declared
local_safe      group, i.e. without code shared across projects; the two
                protocols use the same population and balanced folds, so their
                difference measures the effect of project-disjoint splitting at
                comparable training sizes (differences between projects and the
                effect of duplicates are not isolated causally)
cross           train on the whole source corpus, test on another corpus. The
                DAppSCAN target is its 948 files with any SWC annotation, a
                different population from the within-corpus DAppSCAN runs.

DAppSCAN negatives mean "no published finding of this class", not "verified
safe"; missing labels can bias AUPRC in either direction.

Outputs: results/contracts/<run>/metrics.csv (+ summary), folds.csv (fold sizes and
positives), assignments.parquet (fold id per file, protocol and seed),
oof_scores.parquet / cross_scores.parquet (per-file scores), manifest.json
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import GroupKFold, StratifiedKFold

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bal.data.contracts import label_files, load_all                       # noqa: E402
from bal.eval.metrics import safe_ap, safe_auc                             # noqa: E402
from bal.features.contract_features import (near_duplicate_groups, normalised_text,  # noqa: E402
                                            pattern_matrix, raw_text)
from bal.models.tabular import MODELS                                      # noqa: E402
from bal.utils.repro import atomic_to_csv, set_seed, write_manifest        # noqa: E402

TARGET_CLASSES = ["reentrancy", "arithmetic", "timestamp", "unchecked"]
PAT_MODELS = ["rf", "lgbm", "mlp", "kan"]
WITHIN_PAT_MODELS = ["rf", "lgbm"]
WITHIN_PROTOCOLS = ["random", "random_matched", "project", "safe", "local_random", "local_safe"]
STOCHASTIC = {"rf", "lgbm", "mlp", "kan"}


def union_groups(groups: np.ndarray, comps: np.ndarray) -> np.ndarray:
    """Merge declared groups with near-duplicate components (union-find)."""
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for g, c in zip(groups, comps):
        a, b = find(("g", g)), find(("c", int(c)))
        if a != b:
            parent[b] = a
    return np.array([str(find(("g", g))) for g in groups])


def lex_fit_transform(train_txt, test_txt):
    v = TfidfVectorizer(token_pattern=r"\S+", ngram_range=(1, 3), min_df=2, max_features=50000,
                        sublinear_tf=True, lowercase=False)
    return v.fit_transform(train_txt), v.transform(test_txt)


def run_fold(rep, model, Xtr, ytr, Xte, yte, seed, txt_tr=None, txt_te=None):
    set_seed(seed)
    if rep.startswith("lex"):
        A, B = lex_fit_transform(txt_tr, txt_te)
        m = MODELS["logreg"](seed=seed).fit(A, ytr)
        s = m.predict_score(B)
    else:
        m = MODELS[model](seed=seed).fit(Xtr, ytr)
        s = m.predict_score(Xte)
    return safe_ap(yte, s), safe_auc(yte, s), s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="results/contracts")
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--models", default=",".join(PAT_MODELS))
    ap.add_argument("--protocols", default=",".join(WITHIN_PROTOCOLS),
                    help="within-corpus protocols to run")
    ap.add_argument("--skip-cross", action="store_true")
    a = ap.parse_args()
    run = Path(a.out) / time.strftime("c2_%Y%m%d_%H%M%S")
    run.mkdir(parents=True, exist_ok=True)
    pat_models = a.models.split(",")

    df = load_all()
    df["norm"] = df.source.map(normalised_text)
    df["raw"] = df.source.map(raw_text)
    comps = near_duplicate_groups(df.norm.tolist(), threshold=0.8)
    df["comp"] = comps
    df["safe_group"] = union_groups(df.group.to_numpy(), comps)
    # a component is "local" if all its files belong to one declared group
    df["local"] = df.comp.map(df.groupby("comp").group.nunique()) == 1
    P = pattern_matrix(df.source).to_numpy(dtype=np.float32)

    rows, fold_rows, assign, oof = [], [], [], []

    def log(**kw):
        rows.append(kw)
        print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in kw.items()}, flush=True)

    def group_folds(groups, seed):
        # GroupKFold is deterministic; shuffle group ids per seed
        perm = {u: i for i, u in enumerate(np.random.default_rng(seed).permutation(np.unique(groups)))}
        return GroupKFold(5).split(np.zeros(len(groups)), groups=np.array([perm[x] for x in groups]))

    def make_folds(proto, sub, y, seed):
        if proto in ("random", "local_random"):
            return list(StratifiedKFold(5, shuffle=True, random_state=seed).split(np.zeros(len(y)), y))
        if proto == "project":
            return list(group_folds(sub.group.to_numpy(), seed))
        if proto in ("safe", "local_safe"):
            return list(group_folds(sub.safe_group.to_numpy(), seed))
        if proto == "random_matched":
            rnd = make_folds("random", sub, y, seed)
            safe_sizes = sorted(len(tr) for tr, _ in make_folds("safe", sub, y, seed))
            rng = np.random.default_rng(seed)
            out = []
            for (tr, te), n_tr in zip(sorted(rnd, key=lambda f: len(f[0])), safe_sizes):
                keep = []
                for cls_val in (0, 1):     # stratified sub-sample of the training fold
                    idx_c = tr[y[tr] == cls_val]
                    k = int(round(len(idx_c) * n_tr / len(tr)))
                    keep.append(rng.choice(idx_c, min(k, len(idx_c)), replace=False))
                out.append((np.sort(np.concatenate(keep)), te))
            return out
        raise ValueError(proto)

    # ---- within-corpus -----------------------------------------------------------
    for ds in ["solidifi", "dappscan"]:
        for c in TARGET_CLASSES:
            for proto in a.protocols.split(","):
                sub = df[(df.dataset == ds) & (df.local if proto.startswith("local") else True)]
                sub = sub.reset_index()
                if proto.startswith("local"):
                    # re-derive groups inside the restricted population: links through
                    # removed (cross-project) files must not merge the remaining projects
                    sub["safe_group"] = union_groups(sub.group.to_numpy(), sub.comp.to_numpy())
                idx = sub["index"].to_numpy()
                y = sub[c].to_numpy()
                if y.sum() < 10:
                    continue
                for seed in range(a.seeds):
                    folds = make_folds(proto, sub, y, seed)
                    fold_id = np.full(len(y), -1)
                    for k, (tr, te) in enumerate(folds):
                        fold_id[te] = k
                        fold_rows.append({"dataset": ds, "cls": c, "protocol": proto, "seed": seed, "fold": k,
                                          "n_train": len(tr), "n_test": len(te), "pos_train": int(y[tr].sum()),
                                          "pos_test": int(y[te].sum())})
                    assign.append(pd.DataFrame({"dataset": ds, "cls": c, "protocol": proto, "seed": seed,
                                                "file_id": idx, "fold": fold_id}))
                    for rep, models in [("lex_raw", ["logreg"]), ("lex_norm", ["logreg"]),
                                        ("pat", WITHIN_PAT_MODELS)]:
                        for mname in models:
                            S = np.zeros(len(y))
                            txt = sub["raw" if rep == "lex_raw" else "norm"].to_numpy()
                            for tr, te in folds:
                                _, _, s = run_fold(rep, mname, P[idx[tr]], y[tr], P[idx[te]], y[te], seed,
                                                   txt[tr], txt[te])
                                S[te] = s
                            oof.append(pd.DataFrame({"dataset": ds, "cls": c, "protocol": proto, "seed": seed,
                                                     "rep": rep, "model": mname, "file_id": idx, "y": y, "score": S.astype(np.float32)}))
                            log(setting="within", train=ds, test=ds, protocol=proto, cls=c, rep=rep,
                                model=mname, seed=seed, auprc=safe_ap(y, S), roc_auc=safe_auc(y, S),
                                n_test=int(len(y)), n_pos=int(y.sum()), base_rate=float(y.mean()),
                                mean_n_train=float(np.mean([len(tr) for tr, _ in folds])))

    # ---- cross-corpus ----------------------------------------------------------
    cross = []
    pairs = [("solidifi", "smartbugs"), ("dappscan", "smartbugs"), ("solidifi", "dappscan"),
             ("dappscan", "solidifi")]
    for src, tgt in ([] if a.skip_cross else pairs):
        S_ = df[df.dataset == src]
        T_ = df[df.dataset == tgt]
        if tgt == "dappscan":
            T_ = T_[T_.sb_category == "labelled"]   # only audited files as target
        for c in TARGET_CLASSES:
            ytr, yte = S_[c].to_numpy(), T_[c].to_numpy()
            if ytr.sum() < 10 or yte.sum() < 3:
                continue
            for rep, models in [("lex_raw", ["logreg"]), ("lex_norm", ["logreg"]), ("pat", pat_models)]:
                for mname in models:
                    for seed in range(a.seeds if mname in STOCHASTIC else 1):
                        txt = "raw" if rep == "lex_raw" else "norm"
                        ap_, auc_, sc = run_fold(rep, mname, P[S_.index], ytr, P[T_.index], yte, seed,
                                                 S_[txt].tolist(), T_[txt].tolist())
                        cross.append(pd.DataFrame({"train": src, "test": tgt, "cls": c, "rep": rep,
                                                   "model": mname, "seed": seed, "file_id": T_.index.to_numpy(),
                                                   "y": yte, "score": np.asarray(sc, dtype=np.float32)}))
                        log(setting="cross", train=src, test=tgt, protocol="cross", cls=c, rep=rep,
                            model=mname, seed=seed, auprc=ap_, roc_auc=auc_, n_test=int(len(yte)),
                            n_pos=int(yte.sum()), base_rate=float(yte.mean()))

    met = pd.DataFrame(rows)
    atomic_to_csv(met, run / "metrics.csv", index=False)
    summ = (met.groupby(["setting", "train", "test", "protocol", "cls", "rep", "model"])
               [["auprc", "roc_auc", "base_rate", "mean_n_train"]].agg(["mean", "std"]).round(4))
    atomic_to_csv(summ, run / "metrics_summary.csv")
    atomic_to_csv(pd.DataFrame(fold_rows), run / "folds.csv", index=False)
    pd.concat(assign).to_parquet(run / "assignments.parquet", index=False)
    pd.concat(oof).to_parquet(run / "oof_scores.parquet", index=False)
    if cross:
        pd.concat(cross).to_parquet(run / "cross_scores.parquet", index=False)
    groups = df[["dataset", "path", "group", "comp", "safe_group", "local", *TARGET_CLASSES]].rename_axis("file_id")
    groups.reset_index().to_parquet(run / "groups.parquet", index=False)
    write_manifest(run, script=Path(__file__).name, config=vars(a),
                   data_sets={f"sources_{ds}": g.path for ds, g in df.groupby("dataset")}
                   | {"label_files": label_files()},
                   extra={"target_classes": TARGET_CLASSES, "within_protocols": WITHIN_PROTOCOLS,
                          "within_pat_models": WITHIN_PAT_MODELS})
    print("wrote", run)


if __name__ == "__main__":
    main()
