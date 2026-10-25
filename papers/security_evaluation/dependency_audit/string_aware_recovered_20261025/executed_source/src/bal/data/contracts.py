"""
Smart-contract vulnerability corpora (C), unified to one schema.

Three public corpora with three *different labelling regimes*:

* SmartBugs-curated (Durieux et al., ICSE 2020; smartbugs/smartbugs-curated @230e649)
  143 Solidity files, manually annotated vulnerable lines, DASP categories.
  Regime: MANUAL. Used mainly as an external test set.
* SolidiFI-benchmark (Ghaleb & Pattabiraman, ISSTA 2020; @4b0573e)
  50 real contracts x 7 bug types, bugs INJECTED from code-snippet templates.
  Regime: INJECTED. Known artefact: injected identifiers such as
  `counter_re_ent7`, `bug_tmstmp12` reveal the label (studied in HC.2).
* DAppSCAN-source (Zheng et al., IEEE Transactions on Software Engineering 2024,
  doi:10.1109/TSE.2024.3383422; InPlusLab/DAppSCAN @66a5661)
  21,457 Solidity files of 682 audited DApps; 948 files carry SWC labels
  extracted from 608 audit reports. Regime: AUDIT. Files without a label are
  NOT verified clean (positive-unlabelled setting).

Unified label space (file level, binary per class):

    reentrancy  : SB reentrancy        | SolidiFI Re-entrancy          | SWC-107
    arithmetic  : SB arithmetic        | SolidiFI Overflow-Underflow   | SWC-101
    timestamp   : SB time_manipulation | SolidiFI Timestamp-Dependency | SWC-116
    unchecked   : SB unchecked_low_level_calls | SolidiFI Unchecked-Send,
                  Unhandled-Exceptions | SWC-104
    tx_origin   : (none in SB curated) | SolidiFI tx.origin            | SWC-115
    tod         : SB front_running     | SolidiFI TOD                  | SWC-114

`group` is the unit that must not be split across train and test:
SB = file, SolidiFI = base contract index (same base contract appears in all
7 bug-type folders), DAppSCAN = DApp project directory.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

CLASSES = ["reentrancy", "arithmetic", "timestamp", "unchecked", "tx_origin", "tod"]

SB_MAP = {
    "reentrancy": "reentrancy", "arithmetic": "arithmetic",
    "time_manipulation": "timestamp", "unchecked_low_level_calls": "unchecked",
    "front_running": "tod",
}
SOLIDIFI_MAP = {
    "Re-entrancy": "reentrancy", "Overflow-Underflow": "arithmetic",
    "Timestamp-Dependency": "timestamp", "Unchecked-Send": "unchecked",
    "Unhandled-Exceptions": "unchecked", "tx.origin": "tx_origin", "TOD": "tod",
}
SWC_MAP = {"107": "reentrancy", "101": "arithmetic", "116": "timestamp",
           "104": "unchecked", "115": "tx_origin", "114": "tod"}


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")


def load_smartbugs(root="data/raw/smartbugs-curated") -> pd.DataFrame:
    root = Path(root)
    vul = json.loads(_read(root / "vulnerabilities.json"))
    rows = []
    for v in vul:
        p = root / v["path"]
        labels = {c: 0 for c in CLASSES}
        for x in v["vulnerabilities"]:
            c = SB_MAP.get(x["category"])
            if c:
                labels[c] = 1
        rows.append({"dataset": "smartbugs", "regime": "manual", "path": str(p),
                     "group": f"sb:{v['path']}", "source": _read(p), **labels,
                     "sb_category": Path(v["path"]).parts[1]})
    return pd.DataFrame(rows)


def load_solidifi(root="data/raw/SolidiFI-benchmark") -> pd.DataFrame:
    root = Path(root) / "buggy_contracts"
    rows = []
    for d in sorted(root.iterdir()):
        if not d.is_dir():
            continue
        cls = SOLIDIFI_MAP[d.name]
        for p in sorted(d.glob("buggy_*.sol")):
            k = re.search(r"buggy_(\d+)\.sol", p.name).group(1)
            labels = {c: 0 for c in CLASSES}
            labels[cls] = 1
            rows.append({"dataset": "solidifi", "regime": "injected", "path": str(p),
                         "group": f"solidifi:{k}", "source": _read(p), **labels,
                         "sb_category": d.name})
    return pd.DataFrame(rows)


def load_dappscan(root="data/raw/DAppSCAN/DAppSCAN-source", labelled_only: bool = False,
                  max_unlabelled_per_project: int | None = 20, seed: int = 0) -> pd.DataFrame:
    """Labelled files plus (optionally) a capped sample of unlabelled files per project.

    The cap keeps large monorepos from dominating; the sample is deterministic.
    """
    root = Path(root)
    lab = {}
    for j in (root / "SWCsource").rglob("*.json"):
        try:
            d = json.loads(_read(j))
        except json.JSONDecodeError:
            continue
        fp = d.get("filePath", "")
        cats = set()
        for s in d.get("SWCs", []):
            m = re.match(r"SWC-(\d+)", s.get("category", ""))
            if m and m.group(1) in SWC_MAP:
                cats.add(SWC_MAP[m.group(1)])
        lab[fp] = cats
    rows = []
    contracts = root / "contracts"
    import random
    rng = random.Random(seed)
    for proj in sorted(contracts.iterdir()):
        if not proj.is_dir():
            continue
        files = sorted(proj.rglob("*.sol"))
        unl = []
        for p in files:
            rel = "DAppSCAN-source/" + str(p.relative_to(root))
            if rel in lab:
                cats = lab[rel]
                rows.append(_dapp_row(p, proj.name, cats, labelled=True))
            else:
                unl.append(p)
        if labelled_only:
            continue
        rng.shuffle(unl)
        for p in (unl if max_unlabelled_per_project is None else unl[:max_unlabelled_per_project]):
            rows.append(_dapp_row(p, proj.name, set(), labelled=False))
    return pd.DataFrame(rows)


def _dapp_row(p: Path, project: str, cats: set, labelled: bool) -> dict:
    labels = {c: int(c in cats) for c in CLASSES}
    return {"dataset": "dappscan", "regime": "audit", "path": str(p), "group": f"dapp:{project}",
            "source": _read(p), **labels, "sb_category": "labelled" if labelled else "unlabelled"}


def label_files(smartbugs="data/raw/smartbugs-curated",
                dappscan="data/raw/DAppSCAN/DAppSCAN-source") -> list[Path]:
    """Files that carry labels (SolidiFI labels come from its directory layout)."""
    return [Path(smartbugs) / "vulnerabilities.json", *sorted((Path(dappscan) / "SWCsource").rglob("*.json"))]


def load_all(**kw) -> pd.DataFrame:
    df = pd.concat([load_smartbugs(), load_solidifi(), load_dappscan(**kw)], ignore_index=True)
    return df
