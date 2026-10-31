"""
V2  Do learned detectors on SolidiFI recognise the vulnerability or the injected template?

Population: the 350 SolidiFI buggy files and the 50 original contracts
(`bal.data.solidifi`). Folds: 5, grouped by base contract (the seven buggy
files and the original of one contract are always in the same fold), group
order shuffled per seed. Models and representations as in C2: lex_raw and
lex_norm with logistic regression (TF-IDF fitted on the training fold), pat
with RF and LightGBM.

For a class c (positives: the buggy files of its SolidiFI type(s);
negatives: the buggy files of the other types and the 50 originals):

standard  train on the training folds as they are; on the test fold report
          AUPRC against all negatives, against the other buggy files only and
          against the originals only, and the pair test (share of test bases
          whose buggy file of the class scores above its original; ties ½).
loto      for every template t of c with >= 20 occurrences (classes with at
          least two such templates): training positives lose every snippet of
          t (a file left without snippets is dropped); test positives are the
          buggy files of the test bases that contain t, reduced to t only.
seen      the standard models scored on the loto test set.

Outputs: results/contracts/<run>/v2_metrics.csv (one row per class, setting,
template, representation, model, seed), v2_summary.csv, solidifi_audit.csv
(V1 checks per buggy file), templates.csv, manifest.json
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bal.data import solidifi                                              # noqa: E402
from bal.eval.metrics import safe_ap                                        # noqa: E402
from bal.features.contract_features import normalised_text, pattern_features, raw_text  # noqa: E402
from bal.models.tabular import MODELS                                       # noqa: E402
from bal.utils.repro import atomic_to_csv, set_seed, write_manifest         # noqa: E402

CLASS_TYPES = {"reentrancy": ["Re-entrancy"], "timestamp": ["Timestamp-Dependency"],
               "unchecked": ["Unhandled-Exceptions"], "unprotected_send": ["Unchecked-Send"],
               "arithmetic": ["Overflow-Underflow"], "tx_origin": ["tx.origin"],
               "unchecked_merged": ["Unchecked-Send", "Unhandled-Exceptions"]}   # C2/C3 mapping, sensitivity only
REPS = [("lex_raw", "logreg"), ("lex_norm", "logreg"), ("pat", "rf"), ("pat", "lgbm")]
MIN_OCC = 20


class Featurizer:
    """Text -> raw / normalised token text and pattern vector, cached by content hash."""

    def __init__(self):
        self.cache = {}

    def __call__(self, src: str):
        h = hashlib.sha1(src.encode()).hexdigest()
        if h not in self.cache:
            pf = pattern_features(src)
            self.cache[h] = (raw_text(src), normalised_text(src), np.array(list(pf.values()), np.float32))
        return self.cache[h]


def fit(rep, model, train, ytr, seed):
    """Fitted model as a function: list of featurised texts -> scores."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    set_seed(seed)
    if rep.startswith("lex"):
        i = 0 if rep == "lex_raw" else 1
        v = TfidfVectorizer(token_pattern=r"\S+", ngram_range=(1, 3), min_df=2, max_features=50000,
                            sublinear_tf=True, lowercase=False)
        m = MODELS["logreg"](seed=seed).fit(v.fit_transform([t[i] for t in train]), ytr)
        return lambda test: m.predict_score(v.transform([t[i] for t in test]))
    m = MODELS[model](seed=seed).fit(np.stack([t[2] for t in train]), ytr)
    return lambda test: m.predict_score(np.stack([t[2] for t in test]))


def pair_test(s_pos: dict, s_clean: dict) -> float:
    """Share of (base, buggy file) pairs where the buggy file scores above the original; ties count 1/2."""
    v = [1.0 if s > s_clean[k] else 0.5 if s == s_clean[k] else 0.0 for (k, _), s in s_pos.items()]
    return float(np.mean(v)) if v else float("nan")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="results/contracts")
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--classes", default=",".join(CLASS_TYPES))
    a = ap.parse_args()
    run = Path(a.out) / time.strftime("v2_%Y%m%d_%H%M%S")
    run.mkdir(parents=True, exist_ok=True)

    files, clean, cat = solidifi.load()
    audit = pd.DataFrame(solidifi.verify(files, clean))
    atomic_to_csv(audit, run / "solidifi_audit.csv", index=False)
    occ = pd.Series([s.template for f in files for s in f.snippets]).value_counts()
    tmpl = pd.DataFrame([{"template": tid, "bug_type": t, "n_tokens": len(key), "occurrences": int(occ.get(tid, 0)),
                          "files": sum(any(s.template == tid for s in f.snippets) for f in files)}
                         for t, c in cat.items() for key, tid in c.items()])
    atomic_to_csv(tmpl, run / "templates.csv", index=False)
    print(audit[["base_equal"]].value_counts().to_string(), "| snippets == BugLog rows:",
          int((audit.n_snippets == audit.n_buglog).sum()), "of", len(audit), flush=True)

    F = Featurizer()
    bases = sorted(clean)
    by_key = {(f.bug_type, f.k): f for f in files}
    rows = []

    def log(**kw):
        rows.append(kw)
        print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in kw.items()}, flush=True)

    for cls in a.classes.split(","):
        types = CLASS_TYPES[cls]
        loto_t = [tid for t in types for tid in cat[t].values() if occ.get(tid, 0) >= MIN_OCC]
        if len(loto_t) < 2 or cls.endswith("_merged"):
            loto_t = []
        for seed in range(a.seeds):
            perm = np.random.default_rng(seed).permutation(len(bases))
            gid = {b: int(perm[i]) for i, b in enumerate(bases)}
            folds = GroupKFold(5).split(np.zeros(len(bases)), groups=[gid[b] for b in bases])
            for fold, (tr_i, te_i) in enumerate(folds):
                tr_b, te_b = {bases[i] for i in tr_i}, {bases[i] for i in te_i}

                def population(bset, pos_override=None):
                    """[(key, text, y, kind)] for the bases in bset; kind: pos / other / clean."""
                    out = []
                    for f in files:
                        if f.k not in bset:
                            continue
                        if f.bug_type in types:
                            src = pos_override(f) if pos_override else f.source
                            if src is not None:
                                out.append(((f.k, f.bug_type), src, 1, "pos"))
                        else:
                            out.append(((f.k, f.bug_type), f.source, 0, "other"))
                    out += [((k, "clean"), clean[k], 0, "clean") for k in sorted(bset)]
                    return out

                train = population(tr_b)
                test = population(te_b)
                Xtr, ytr = [F(t) for _, t, _, _ in train], np.array([y for _, _, y, _ in train])
                Xte = [F(t) for _, t, _, _ in test]
                kind = np.array([k for _, _, _, k in test])
                yte = (kind == "pos").astype(int)

                # loto test sets (shared by `seen` and `loto`)
                loto_sets = {}
                for tid in loto_t:
                    ttype = tid.split("/")[0]
                    pos = [((f.k, f.bug_type), f.only({tid}), 1, "pos") for f in files
                           if f.k in te_b and f.bug_type == ttype and any(s.template == tid for s in f.snippets)]
                    neg = [r for r in test if r[3] != "pos"]
                    loto_sets[tid] = pos + neg

                for rep, model in REPS:
                    std = fit(rep, model, Xtr, ytr, seed)
                    s = std(Xte)
                    m_other = kind != "clean"
                    m_clean = kind != "other"
                    s_pos = {test[i][0]: s[i] for i in range(len(test)) if kind[i] == "pos"}
                    s_cl = {test[i][0][0]: s[i] for i in range(len(test)) if kind[i] == "clean"}
                    common = dict(cls=cls, rep=rep, model=model, seed=seed, fold=fold)
                    log(setting="standard", template="-", **common, auprc=safe_ap(yte, s),
                        auprc_vs_other=safe_ap(yte[m_other], s[m_other]),
                        auprc_vs_clean=safe_ap(yte[m_clean], s[m_clean]),
                        pair=pair_test(s_pos, s_cl), n_pos=int(yte.sum()), n=len(yte))
                    for tid, tset in loto_sets.items():
                        if not any(r[3] == "pos" for r in tset):
                            continue
                        Xt = [F(t) for _, t, _, _ in tset]
                        yt = np.array([y for _, _, y, _ in tset])
                        kt = np.array([k for _, _, _, k in tset])
                        # seen: the standard model on the loto test set
                        s_seen = std(Xt)
                        # loto: retrain without template tid
                        tr_l = population(tr_b, pos_override=lambda f, tid=tid: (
                            None if f.snippets and all(x.template == tid for x in f.snippets)
                            else f.only({x.template for x in f.snippets} - {tid})))
                        Xl, yl = [F(t) for _, t, _, _ in tr_l], np.array([y for _, _, y, _ in tr_l])
                        s_loto = fit(rep, model, Xl, yl, seed)(Xt)
                        for setting, sc in (("seen", s_seen), ("loto", s_loto)):
                            sp = {tset[i][0]: sc[i] for i in range(len(tset)) if kt[i] == "pos"}
                            scl = {tset[i][0][0]: sc[i] for i in range(len(tset)) if kt[i] == "clean"}
                            mc = kt != "other"
                            log(setting=setting, template=tid, **common, auprc=safe_ap(yt, sc),
                                auprc_vs_other=safe_ap(yt[kt != "clean"], sc[kt != "clean"]),
                                auprc_vs_clean=safe_ap(yt[mc], sc[mc]), pair=pair_test(sp, scl),
                                n_pos=int(yt.sum()), n=len(yt))
        met = pd.DataFrame(rows)
        atomic_to_csv(met, run / "v2_metrics.csv", index=False)

    met = pd.DataFrame(rows)
    # pooled over folds: mean of fold values (folds have 10 bases each)
    summ = (met.groupby(["cls", "setting", "template", "rep", "model"])
               [["auprc", "auprc_vs_other", "auprc_vs_clean", "pair"]].mean().round(4))
    atomic_to_csv(summ, run / "v2_summary.csv")
    write_manifest(run, script=Path(__file__).name, config=vars(a),
                   data_files=[f.path for f in files] + [Path("data/raw/SolidiFI/contracts") / f"{k}.sol" for k in bases],
                   extra={"class_types": CLASS_TYPES, "reps": REPS, "min_occurrences": MIN_OCC})
    print("wrote", run)


if __name__ == "__main__":
    main()
