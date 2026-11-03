"""V10  Paired edits: does a learned detector follow the weakness or the injected text?

Prompted by an external review (protocol amendment 6). For every SolidiFI
template read as `yes` or `limited` in V1 (34 templates of five classes), a
minimally fixed version was written by hand (data/controls/solidifi_fixed/):
the same code with the weakness removed (state update before the call, return
value required, bound check before the arithmetic, msg.sender instead of
tx.origin, block number instead of timestamp), names and comments kept.

Test unit: base contract k with only the snippets of template t inserted (the
`loto` test file of V2: every occurrence of t in buggy_k, not a single snippet).
Variants of that unit:

  vuln           as injected
  fixed          every snippet of t replaced by its fixed version
  renamed        vuln with comments removed and benchmark identifiers renamed
  fixed_renamed  fixed, renamed in the same way
  clean          the original contract k without any snippet

Expected behaviour of a detector that follows the weakness: vuln > fixed,
vuln ~ renamed, fixed ~ clean. Models: the V2 standard models (5 folds grouped
by base contract, 3 seeds; trained on the full buggy files and originals of the
training bases), so every scored unit comes from a base contract not seen in
training. Every variant file is compiled once per template with solc 0.5.x.

Outputs: results/contracts/v10_<time>/v10_scores.csv (one row per unit, variant,
model, seed), v10_summary.csv, v10_compile.csv, manifest.json

    python scripts/v10_paired_edits.py
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from bal.data import solidifi                                         # noqa: E402
from bal.utils.repro import atomic_to_csv, write_manifest             # noqa: E402
from c3_slither_baseline import ensure_solc, solc_candidates          # noqa: E402
from v2_template_controls import CLASS_TYPES, REPS, Featurizer, fit   # noqa: E402

FIXED = Path("data/controls/solidifi_fixed")
BUGS = Path("data/raw/SolidiFI/bugs")
AUDIT = Path("results/contracts/v1_20261030_181838/template_audit.csv")
CLASSES = ["reentrancy", "timestamp", "unchecked", "arithmetic", "tx_origin"]
_TOK = solidifi._TOK
BENCH_NAME = re.compile(r"\b\w*(?:re_ent|unchk|uncheck|intou|ovrflow|undrflow|tmstmp|txorigin|vundflw|bugv)\w*\b"
                        r"|\b(?:bug_\w+|callnotchecked\w*|unhandledsend\w*|UncheckedExternalCall\w*)\b")


def raw_tokens(src: str) -> list[str]:
    blank = solidifi._blank_comments(src)
    return [m.group() for m in _TOK.finditer(blank)]


def instantiate(example: str, fixed_example: str, actual: str) -> str:
    """Fixed version of `actual`, an instance of the template whose example is `example`."""
    ex, ac = raw_tokens(example), raw_tokens(actual)
    assert len(ex) == len(ac), "instance does not align with the template example"
    mp = {}
    for e, a in zip(ex, ac):
        if e != a:
            mp.setdefault(e, a)
    suffix = {}
    for e, a in mp.items():
        me, ma = re.match(r"(.*?)(\d+)$", e), re.match(r"(.*?)(\d+)$", a)
        if me and ma and me.group(1) == ma.group(1):
            suffix[me.group(2)] = ma.group(2)

    def tok(m):
        t = m.group()
        if t in mp:
            return mp[t]
        s = re.match(r"(.*?\D)(\d+)$", t)
        if s and s.group(2) in suffix and (t[0].isalpha() or t[0] == "_"):
            return s.group(1) + suffix[s.group(2)]
        return t
    out, pos = [], 0
    blank = solidifi._blank_comments(fixed_example)
    for m in _TOK.finditer(blank):
        out.append(fixed_example[pos:m.start()])
        out.append(tok(m))
        pos = m.end()
    out.append(fixed_example[pos:])
    return "".join(out)


def rename(src: str, region: tuple[int, int] | None = None) -> str:
    """Comments removed and benchmark identifiers renamed (consistently within the file)."""
    names = {}
    src = re.sub(r"/\*.*?\*/|//[^\n]*", "", src, flags=re.S)
    return BENCH_NAME.sub(lambda m: names.setdefault(m.group(), f"v{len(names) + 1}"), src)


def variants(f: solidifi.BuggyFile, tid: str, example: str, fixed_example: str) -> dict[str, str]:
    keep = [s for s in f.snippets if s.template == tid]
    cut = sorted((s.char_start, s.char_end, s) for s in f.snippets if s.template != tid)
    # reduce to t only, remembering where the kept snippets end up
    src, pos, parts = f.source, 0, []
    spans = sorted([(s.char_start, s.char_end, "keep") for s in keep] + [(a, b, "cut") for a, b, _ in cut])
    vuln, fixed = [], []
    for a, b, kind in spans:
        vuln.append(src[pos:a]), fixed.append(src[pos:a])
        if kind == "keep":
            vuln.append(src[a:b]), fixed.append(instantiate(example, fixed_example, src[a:b]))
        pos = b
    vuln.append(src[pos:]), fixed.append(src[pos:])
    v, fx = "".join(vuln), "".join(fixed)
    return {"vuln": v, "fixed": fx, "renamed": rename(v), "fixed_renamed": rename(fx)}


def compiles(src: str) -> tuple[bool, str]:
    cands, _ = solc_candidates(src)
    if not cands:
        return False, "no solc"
    solc = ensure_solc(cands[0])
    with tempfile.NamedTemporaryFile("w", suffix=".sol", delete=False) as fh:
        fh.write(src)
    r = subprocess.run([str(solc), "--bin", fh.name], capture_output=True, text=True)
    Path(fh.name).unlink()
    err = re.findall(r"Error: ([^\n]+)", r.stderr)
    return r.returncode == 0, " | ".join(err)[:300]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="results/contracts")
    ap.add_argument("--seeds", type=int, default=3)
    a = ap.parse_args()
    run = Path(a.out) / time.strftime("v10_%Y%m%d_%H%M%S")
    run.mkdir(parents=True, exist_ok=True)

    files, clean, cat = solidifi.load()
    audit = pd.read_csv(AUDIT).set_index("template")
    fixed_t = {p.stem.replace("__", "/"): p.read_text().rstrip("\n") for p in FIXED.glob("*.txt")}
    example = {tid: (BUGS / audit.loc[tid, "example_file"]).read_text(encoding="utf-8", errors="replace")
               for tid in fixed_t}

    # build all variants; compile one unit per template and variant
    units, comp = [], []
    for f in files:
        for tid in sorted({s.template for s in f.snippets} & set(fixed_t)):
            units.append((f, tid, variants(f, tid, example[tid], fixed_t[tid])))
    seen = set()
    for f, tid, var in units:
        if tid in seen:
            continue
        seen.add(tid)
        for name, src in var.items():
            ok, err = compiles(src)
            comp.append({"template": tid, "file": f"{f.bug_type}/buggy_{f.k}", "variant": name,
                         "compiles": ok, "errors": err})
    C = pd.DataFrame(comp)
    atomic_to_csv(C, run / "v10_compile.csv", index=False)
    print(C.groupby("variant").compiles.agg(["sum", "count"]).to_string(), flush=True)
    if not C.compiles.all():
        print(C[~C.compiles].to_string())

    F = Featurizer()
    bases = sorted(clean)
    rows = []
    for cls in CLASSES:
        types = CLASS_TYPES[cls]
        cls_units = [(f, tid, var) for f, tid, var in units if f.bug_type in types]
        for seed in range(a.seeds):
            perm = np.random.default_rng(seed).permutation(len(bases))
            gid = {b: int(perm[i]) for i, b in enumerate(bases)}
            for fold, (tr_i, te_i) in enumerate(GroupKFold(5).split(np.zeros(len(bases)),
                                                                     groups=[gid[b] for b in bases])):
                tr_b, te_b = {bases[i] for i in tr_i}, {bases[i] for i in te_i}
                train = [(f.source, int(f.bug_type in types)) for f in files if f.k in tr_b] + \
                        [(clean[k], 0) for k in sorted(tr_b)]
                Xtr, ytr = [F(t) for t, _ in train], np.array([y for _, y in train])
                test = []
                for f, tid, var in cls_units:
                    if f.k in te_b:
                        test += [(f.k, tid, name, src) for name, src in var.items()]
                        test.append((f.k, tid, "clean", clean[f.k]))
                if not test:
                    continue
                Xte = [F(t[3]) for t in test]
                for rep, model in REPS:
                    s = fit(rep, model, Xtr, ytr, seed)(Xte)
                    rows += [{"cls": cls, "rep": rep, "model": model, "seed": seed, "fold": fold, "base": k,
                              "template": tid, "reading": audit.loc[tid, "reading"], "variant": name,
                              "score": float(sc)} for (k, tid, name, _), sc in zip(test, s)]
            print(cls, "seed", seed, len(rows), flush=True)
    S = pd.DataFrame(rows)
    atomic_to_csv(S, run / "v10_scores.csv", index=False)

    # per unit and model: seed-mean score per variant, then comparisons
    W = S.groupby(["cls", "rep", "model", "template", "reading", "base", "variant"]).score.mean().unstack("variant")

    def frac_gt(x, y):
        return float(np.mean(np.where(x > y, 1.0, np.where(x == y, 0.5, 0.0))))
    summ = []
    for (cls, rep, model, tid, reading), g in W.groupby(level=[0, 1, 2, 3, 4]):
        span = g.vuln - g.clean
        summ.append({"cls": cls, "rep": rep, "model": model, "template": tid, "reading": reading, "units": len(g),
                     **{f"mean_{v}": g[v].mean() for v in ["vuln", "fixed", "renamed", "fixed_renamed", "clean"]},
                     "p_vuln_gt_fixed": frac_gt(g.vuln, g.fixed),
                     "p_renamed_gt_fixed_renamed": frac_gt(g.renamed, g.fixed_renamed),
                     "fix_effect": float(np.median((g.vuln - g.fixed) / span.where(span.abs() > 1e-9))),
                     "rename_effect": float(np.median((g.vuln - g.renamed) / span.where(span.abs() > 1e-9)))})
    U = pd.DataFrame(summ)
    atomic_to_csv(U, run / "v10_summary.csv", index=False)
    pd.set_option("display.width", 250)
    print(U.groupby(["cls", "rep", "model"])[["mean_vuln", "mean_fixed", "mean_renamed", "mean_clean",
                                               "p_vuln_gt_fixed", "fix_effect", "rename_effect"]].mean().round(3))
    write_manifest(run, script=Path(__file__).name, config=vars(a),
                   data_sets={"fixed_templates": sorted(str(p) for p in FIXED.glob("*.txt"))},
                   extra={"templates": sorted(fixed_t)})
    print(f"wrote {run}")


if __name__ == "__main__":
    main()
