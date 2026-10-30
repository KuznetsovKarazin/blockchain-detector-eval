"""
V6  Tables (LaTeX) and figures (PDF) of the V study, computed from the run folders.

Every number in the generated tables is read from a run file; nothing is
typed by hand. Usage:

    python scripts/v6_paper_tables_figures.py --v1 results/contracts/v1_* --v2 results/contracts/v2_* \
        --v3 results/contracts/v3_* --v5 results/contracts/v5_* --out results/contracts/v6_paper
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt                      # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402

BLUE, ORANGE, AQUA, GREY = "#2a78d6", "#eb6834", "#1baf7a", "#8a8984"
INK, INK2 = "#0b0b0b", "#52514e"
SEQ = LinearSegmentedColormap.from_list("seq", ["#fcfcfb", "#cde2fb", "#86b6ef", "#3987e5", "#1c5cab"])
CLS = {"reentrancy": "Reentrancy", "timestamp": "Timestamp", "unchecked": "Unchecked call",
       "arithmetic": "Arithmetic", "tx_origin": "tx.origin", "unprotected_send": "Unprotected send",
       "unchecked_merged": "Unchecked (merged)"}
TOOLS = {"slither": "Slither", "slither_full": "Slither (all)", "mythril": "Mythril", "smartcheck": "SmartCheck"}
DS = {"smartbugs": "SB", "dappscan": "DS", "solidifi": "SF"}
plt.rcParams.update({"font.size": 8, "axes.edgecolor": INK2, "axes.labelcolor": INK, "xtick.color": INK2,
                     "ytick.color": INK2, "axes.spines.top": False, "axes.spines.right": False,
                     "pdf.fonttype": 42, "font.family": "DejaVu Sans"})


def f3(x):
    return "--" if pd.isna(x) else f"{x:.3f}"


def f2(x):
    return "--" if pd.isna(x) else f"{x:.2f}"


def tab_rq2(v1: Path, v2: Path, out: Path):
    m = pd.read_csv(v2 / "v2_metrics.csv")
    reading = pd.read_csv(v1 / "template_audit.csv").set_index("template").reading
    reps = [("lex_raw", "logreg", r"\textsc{lex\_raw}"), ("lex_norm", "logreg", r"\textsc{lex\_norm}"),
            ("pat", "rf", r"\textsc{pat}/RF"), ("pat", "lgbm", r"\textsc{pat}/LGBM")]
    rows, std_all = [], []
    for cls in ["reentrancy", "timestamp", "unchecked", "arithmetic", "tx_origin"]:
        cells = []
        for rep, model, _ in reps:
            x = m[(m.cls == cls) & (m.rep == rep) & (m.model == model)]
            std = x[x.setting == "standard"].auprc.mean()
            # template means first (each template weighs the same), then mean over templates
            seen = x[x.setting == "seen"].groupby("template").auprc.mean().mean()
            loto = x[x.setting == "loto"].groupby("template").auprc.mean().mean()
            cells += [f3(seen), f3(loto)]
            std_all.append(std)
        n_t = m[(m.cls == cls) & (m.setting == "loto")].template.nunique()
        rows.append(f"{CLS[cls]} ({n_t}) & " + " & ".join(cells) + r"\\")
    # templates grouped by the author's reading (V1), over the five classes above
    m5 = m[m.cls.isin(["reentrancy", "timestamp", "unchecked", "arithmetic", "tx_origin"])
           & m.setting.isin(["seen", "loto"])].copy()
    m5["reading"] = m5.template.map(reading)
    rows.append("\\midrule")
    for rd in ("yes", "limited", "no"):
        cells = []
        for rep, model, _ in reps:
            x = m5[(m5.reading == rd) & (m5.rep == rep) & (m5.model == model)]
            t = x.groupby(["setting", "template"]).auprc.mean().groupby("setting").mean()
            cells += [f3(t.get("seen")), f3(t.get("loto"))]
        n_t = m5[m5.reading == rd].template.nunique()
        rows.append(f"Read as \\emph{{{rd}}} ({n_t}) & " + " & ".join(cells) + r"\\")
    head = (r"\begin{tabular}{@{}l" + "rr" * 4 + r"@{}}" "\n\\toprule\n"
            + " & " + " & ".join(rf"\multicolumn{{2}}{{c}}{{{n}}}" for _, _, n in reps) + r"\\" "\n"
            + "".join(rf"\cmidrule(lr){{{2 + 2 * i}-{3 + 2 * i}}}" for i in range(4)) + "\n"
            + "Class (templates) & " + " & ".join(["seen", "LOTO"] * 4) + r"\\" "\n\\midrule\n")
    (out / "tab_rq2_std_range.txt").write_text(f"{min(std_all):.3f}--{max(std_all):.3f}\n")
    (out / "tab_rq2.tex").write_text(head + "\n".join(rows) + "\n\\bottomrule\n\\end{tabular}\n")


def short_model(c: str) -> str:
    """lex_raw/logreg/C=0.1 -> raw-LR 0.1; pat/lgbm -> pat-LGBM."""
    p = c.split("/")
    if p[0] == "pat":
        return "pat-" + {"rf": "RF", "lgbm": "LGBM", "mlp": "MLP"}[p[1]]
    return f"{p[0][4:]}-LR {p[2][2:]}"


def tab_rq4(v3: Path, out: Path):
    s = pd.read_csv(v3 / "v3_selection.csv")
    rows = []
    for r in s.itertuples():
        cand, orc = short_model(r.candidate), short_model(r.oracle)
        rows.append(f"{CLS[r.cls]} & {DS[r.source]}$\\rightarrow${DS[r.target]} & {cand} & {r.auprc:.3f} "
                    f"({r.ci_lo:.3f}--{r.ci_hi:.3f}) & {r.base_rate:.3f} & {orc} & {r.oracle_auprc:.3f} & {int(r.rank_on_target)}\\\\")
    head = ("\\begin{tabular}{@{}llllrlrr@{}}\n\\toprule\nClass & Pair & Frozen model & AP (95\\% CI) & Chance & "
            "Oracle model & AP & Rank\\\\\n\\midrule\n")
    (out / "tab_rq4.tex").write_text(head + "\n".join(rows) + "\n\\bottomrule\n\\end{tabular}\n")


def tab_rq3(v5: Path, out: Path):
    fl = pd.read_csv(v5 / "tool_file_level.csv")
    lo = pd.read_csv(v5 / "solidifi_located.csv")
    rows = []
    for tool in ["slither", "slither_full", "mythril", "smartcheck"]:
        # all detectors differ from the default configuration only for reentrancy
        for cls in (["reentrancy"] if tool == "slither_full" else
                    ["reentrancy", "timestamp", "unchecked", "arithmetic", "tx_origin", "unprotected_send", "unchecked_merged"]):
            L = lo[(lo.tool == tool) & (lo.cls == cls)]
            if L.empty or L.n_pos.iloc[0] == 0:
                continue
            L = L.iloc[0]
            sf = fl[(fl.tool == tool) & (fl.dataset == "solidifi") & (fl.cls == cls) & (fl.scope == "end_to_end")]
            sb = fl[(fl.tool == tool) & (fl.dataset == "smartbugs") & (fl.cls == cls) & (fl.scope == "end_to_end")]
            # precision is undefined when the tool flags nothing
            prec = f2(sf.precision.iloc[0]) if len(sf) and sf.tp.iloc[0] + sf.fp.iloc[0] > 0 else "--"
            sbp = f2(sb.precision.iloc[0]) if len(sb) and sb.tp.iloc[0] + sb.fp.iloc[0] > 0 else "--"
            sbpr = f"{sbp} / {f2(sb.recall.iloc[0])}" if len(sb) else "--"
            rows.append(f"{TOOLS[tool]} & {CLS[cls]} & {int(L.n_pos_analysed)}/{int(L.n_pos)} & {f2(L.file_recall)} & "
                        f"{f2(L.snippet_recall)} & {prec} & {f2(L.flag_rate_originals)} & {sbpr}\\\\")
    head = ("\\begin{tabular}{@{}llrrrrrr@{}}\n\\toprule\n & & \\multicolumn{5}{c}{SolidiFI} & SmartBugs\\\\\n"
            "\\cmidrule(lr){3-7}\\cmidrule(lr){8-8}\nTool & Class & analysed & file R & snip.\\ R & file P & "
            "orig.\\ flagged & P / R\\\\\n\\midrule\n")
    (out / "tab_rq3.tex").write_text(head + "\n".join(rows) + "\n\\bottomrule\n\\end{tabular}\n")


def tab_rq5(v5: Path, out: Path):
    p = pd.read_csv(v5 / "budget_points.csv")
    p = p[(p.target == "smartbugs") & (p.tool.isin(["slither", "mythril", "smartcheck"]))]
    rows = []
    for (tool, cls, src), g in p.groupby(["tool", "cls", "source"], sort=False):
        g = g.set_index("k")
        kt = int(g[g.k_is_tool_alarms].index[0]) if g.k_is_tool_alarms.any() else None
        cells = []
        for k in (5, 20):
            if k not in g.index:
                cells += ["--"] * 3
                continue
            r = g.loc[k]
            cells += [f2(r.tool_recall), f2(r.model_recall), f2(r.hybrid_recall)]
        rt = g.loc[kt] if kt is not None else None
        rows.append(f"{TOOLS[tool]} & {CLS[cls]} & {DS[src]} & {int(g.n_pos.iloc[0])} & " + " & ".join(cells)
                    + (f" & {kt} & {f2(rt.tool_recall)} & {f2(rt.model_recall)}" if rt is not None else " & -- & -- & --")
                    + r"\\")
    head = ("\\begin{tabular}{@{}lllr" + "rrr" * 2 + "rrr@{}}\n\\toprule\n & & & & "
            + " & ".join(rf"\multicolumn{{3}}{{c}}{{$k={k}$}}" for k in (5, 20))
            + r" & \multicolumn{3}{c}{$k=$ tool alarms}\\" "\n"
            + "".join(rf"\cmidrule(lr){{{5 + 3 * i}-{7 + 3 * i}}}" for i in range(3)) + "\n"
            + "Tool & Class & Src & Pos & " + " & ".join(["T", "M", "H"] * 2) + r" & $k$ & T & M\\" "\n\\midrule\n")
    (out / "tab_rq5.tex").write_text(head + "\n".join(rows) + "\n\\bottomrule\n\\end{tabular}\n")


def fig_templates(v1: Path, v2: Path, v5: Path, out: Path):
    """Snippet recall of each tool and seen / LOTO AP of lex_raw per template."""
    aud = pd.read_csv(v1 / "template_audit.csv").set_index("template")
    t = pd.read_csv(v5 / "solidifi_templates.csv")
    t = t[~t.cls.str.endswith("_merged")]
    tools = [c for c in ["slither", "slither_full", "mythril", "smartcheck"] if c in set(t.tool)]
    piv = t.pivot_table(index="template", columns="tool", values="snippet_recall")
    m = pd.read_csv(v2 / "v2_metrics.csv")
    ml = m[(m.rep == "lex_raw") & m.setting.isin(["seen", "loto"])].groupby(["template", "setting"]).auprc.mean().unstack()
    order = [x for x in aud.index if x.split("/")[0] not in ("TOD", "Unchecked-Send")]
    cols = [(TOOLS[c], piv.reindex(order)[c] if c in piv else pd.Series(np.nan, index=order)) for c in tools]
    cols += [("lex_raw seen AP", ml.reindex(order)["seen"]), ("lex_raw LOTO AP", ml.reindex(order)["loto"])]
    M = np.column_stack([c[1].to_numpy(dtype=float) for c in cols])
    fig, ax = plt.subplots(figsize=(6.3, 7.4))
    ax.imshow(np.ma.masked_invalid(M), cmap=SEQ, vmin=0, vmax=1, aspect="auto")
    for i in range(M.shape[0]):
        for j in range(M.shape[1]):
            v = M[i, j]
            ax.text(j, i, "" if np.isnan(v) else f"{v:.2f}", ha="center", va="center", fontsize=6,
                    color="#fcfcfb" if (not np.isnan(v) and v > 0.62) else INK)
    mark = {"yes": "", "limited": " (ltd)", "no": " (no)"}
    ax.set_yticks(range(len(order)), [f"{x}{mark[aud.loc[x, 'reading']]}" for x in order], fontsize=6)
    ax.set_xticks(range(len(cols)), [c[0] for c in cols], rotation=30, ha="right")
    for i, x in enumerate(order):
        if aud.loc[x, "reading"] != "yes":
            ax.get_yticklabels()[i].set_color(ORANGE if aud.loc[x, "reading"] == "no" else INK2)
    prev = None
    for i, x in enumerate(order):
        if prev is not None and x.split("/")[0] != prev:
            ax.axhline(i - 0.5, color="#fcfcfb", lw=2)
        prev = x.split("/")[0]
    ax.axvline(len(tools) - 0.5, color="#fcfcfb", lw=3)
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    fig.tight_layout()
    fig.savefig(out / "fig_templates.pdf")
    plt.close(fig)


def fig_budget(v5: Path, out: Path):
    c = pd.read_parquet(v5 / "budget_curves.parquet")
    c = c[c.target == "smartbugs"]
    panels = [("slither", "reentrancy"), ("slither", "unchecked"), ("slither", "timestamp"), ("mythril", "arithmetic")]
    fig, axes = plt.subplots(1, 4, figsize=(7.0, 2.1), sharey=True)
    for ax, (tool, cls) in zip(axes, panels):
        g = c[(c.tool == tool) & (c.cls == cls)]
        if g.empty:
            ax.set_visible(False)
            continue
        src = "dappscan" if cls in ("unchecked",) else "solidifi"
        g = g[g.source == src]
        for det, col, lab, lw in (("hybrid", AQUA, "hybrid", 2.6), ("tool", BLUE, "tool", 1.6),
                                  ("model", ORANGE, "model", 1.4)):
            h = g[g.detector == det].sort_values("k")
            ax.plot(h.k, h.recall, color=col, lw=lw, label=lab)
        n = int(g.k.max())
        ax.set_title(f"{CLS[cls]}\n{TOOLS[tool]}, model from {DS[src]}", fontsize=7.5, color=INK)
        ax.set_xlim(0, min(n, 80))
        ax.set_xlabel("files inspected (k)")
        ax.grid(axis="y", color="#e7e6e2", lw=0.6)
    axes[0].set_ylabel("recall")
    axes[0].legend(frameon=False, fontsize=6.5, loc="lower right")
    fig.tight_layout()
    fig.savefig(out / "fig_budget.pdf")
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    for k in ("v1", "v2", "v3", "v5"):
        ap.add_argument(f"--{k}", required=True)
    ap.add_argument("--out", default="results/contracts/v6_paper")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    tab_rq2(Path(a.v1), Path(a.v2), out)
    tab_rq4(Path(a.v3), out)
    tab_rq3(Path(a.v5), out)
    tab_rq5(Path(a.v5), out)
    fig_templates(Path(a.v1), Path(a.v2), Path(a.v5), out)
    fig_budget(Path(a.v5), out)
    print("wrote", out)


if __name__ == "__main__":
    main()
