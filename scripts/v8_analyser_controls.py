"""V8  Positive and negative controls for the static analysers (protocol amendment 4).

Fifteen minimal contracts in data/controls/swc/, written for this study: for each
class a vulnerable version and a minimally fixed version (plus a send/transfer
reentrancy variant). Every analyser configuration of V4 runs on every file;
Mythril additionally runs without `--solv` (the V4 configuration before
amendment 4), which shows why it reported no SWC-101 finding: without a known
compiler version Mythril disables its IntegerArithmetics module.

A useful analyser flags the `_vuln` file of a class it has a rule for and does
not flag the `_fixed` file. Slither is mapped twice for unprotected Ether
transfers: without a rule (V5) and with `arbitrary-send-eth` (amendment 4).

Output: results/contracts/v8_<time>/controls.csv (one row per tool, file, class)
and findings.json.

    MYTH=... SMARTCHECK=... JAXB_DIR=... python scripts/v8_analyser_controls.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import v4_static_tools as v4                                    # noqa: E402
from bal.utils.repro import atomic_to_csv, write_manifest      # noqa: E402
from v5_tools_lines_budget import MAPPING                      # noqa: E402

CTRL = Path("data/controls/swc")
CLASS_OF = {"reentrancy": "reentrancy", "unchecked": "unchecked", "arithmetic": "arithmetic",
            "timestamp": "timestamp", "txorigin": "tx_origin", "unprotected": "unprotected_send"}
MAP = {k: dict(v) for k, v in MAPPING.items()}
MAP["slither_asend"] = {**MAP["slither"], "unprotected_send": {"arbitrary-send-eth"}}
MAP["slither_full_asend"] = {**MAP["slither_full"], "unprotected_send": {"arbitrary-send-eth"}}
MAP["mythril_nosolv"] = MAP["mythril"]


def main() -> None:
    run = Path("results/contracts") / time.strftime("v8_%Y%m%d_%H%M%S")
    run.mkdir(parents=True, exist_ok=True)
    a = SimpleNamespace(timeout=600, exec_timeout=90)
    raw, rows = {}, []
    for f in sorted(CTRL.glob("*.sol")):
        src = f.read_text()
        cls = CLASS_OF[f.stem.split("_")[0]]
        variant = f.stem.split("_")[-1]
        res = {"slither": v4.run_compiled("slither", str(f), src, a),
               "slither_full": v4.run_compiled("slither_full", str(f), src, a),
               "mythril": v4.run_compiled("mythril", str(f), src, a),
               "smartcheck": v4.smartcheck(str(f), a.timeout)}
        cands, _ = v4.solc_candidates(src)
        res["mythril_nosolv"] = v4.mythril_once(str(f), cands[0], a.timeout, a.exec_timeout, solv=False)
        res["slither_asend"], res["slither_full_asend"] = res["slither"], res["slither_full"]
        raw[f.name] = res
        for tool, r in res.items():
            rules = MAP[tool].get(cls)
            hit = sorted({x["rule"] for x in r.get("findings", []) if rules and x["rule"] in rules})
            rows.append({"file": f.name, "class": cls, "variant": variant, "tool": tool, "status": r["status"],
                         "has_rule": bool(rules), "flagged": bool(hit), "rules_hit": ";".join(hit),
                         "all_rules": ";".join(sorted({x["rule"] for x in r.get("findings", [])}))})
        print(f.name, {t: r["status"] for t, r in res.items()}, flush=True)
    R = pd.DataFrame(rows)
    atomic_to_csv(R, run / "controls.csv", index=False)
    (run / "findings.json").write_text(json.dumps(raw, indent=1))
    piv = R[R.has_rule].pivot_table(index=["class", "file"], columns="tool", values="flagged", aggfunc="first")
    print(piv.replace({True: "X", False: "."}).to_string())
    write_manifest(run, script=Path(__file__).name, config={"timeout": 600, "exec_timeout": 90},
                   data_sets={"controls": [str(p) for p in sorted(CTRL.glob("*.sol"))]})
    print(f"wrote {run}")


if __name__ == "__main__":
    main()
