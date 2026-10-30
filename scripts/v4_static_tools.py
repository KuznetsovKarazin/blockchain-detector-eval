"""
V4  Three static analysers on the same files, with line numbers and failure accounting.

Tools: Slither 0.11.6 (static, SlithIR; `slither` excludes informational and
optimisation detectors as C3 does, `slither_full` keeps them), Mythril 0.24.8 (symbolic execution),
SmartCheck 2.0.1 (XPath rules on the parse tree, no compiler). Files:
SmartBugs-curated (143), SolidiFI buggy files (350), the 50 original SolidiFI
contracts, and with `--dappscan` the 948 annotated DAppSCAN files (SmartCheck
only).

Slither and Mythril compile with the compiler choice of C3 (newest allowed
minor of the pragma range first, older minors after a failure). Every
(tool, file) gets a status: ok, compile_error, timeout, tool_error or
unsupported_pragma. Raw results are cached per file (`raw/<tool>/<id>.json`),
so an interrupted run continues with `--resume <run>`.

Each finding is stored with its rule (Slither check, Mythril SWC id,
SmartCheck rule id) and its lines in the analysed file: for Slither the lines
of the most specific source element (a `node` element if there is one, else
the first element), for Mythril `lineno`, for SmartCheck `line`. The class
mapping is applied later (v5_tools_lines_budget.py), so this script records
every finding.

Environment
-----------
    MYTH        path of the `myth` executable (own venv; default: `myth` on PATH)
    SMARTCHECK  path of smartcheck-2.0-jar-with-dependencies.jar
    JAXB_DIR    folder with jaxb-api, jaxb-runtime, activation, istack and txw2
                jars (needed on Java >= 11)

Usage
-----
    python scripts/v4_static_tools.py --tools slither,smartcheck,mythril --workers 3 [--dappscan]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from bal.data.contracts import load_dappscan, load_smartbugs   # noqa: E402
from bal.data import solidifi                                  # noqa: E402
from bal.utils.repro import write_manifest                     # noqa: E402
from c3_slither_baseline import (_is_compile_failure, _tail, ensure_solc,  # noqa: E402
                                 solc_candidates)

BIN = Path(shutil.which("slither") or Path(sys.executable).parent / "slither").parent
CLEAN_DIR = Path("data/derived/solidifi_clean")


def file_table(with_dappscan: bool) -> pd.DataFrame:
    sb = load_smartbugs()[["dataset", "path", "source"]]
    files, clean, _ = solidifi.load()
    sf = pd.DataFrame({"dataset": "solidifi", "path": [str(f.path) for f in files],
                       "source": [f.source for f in files]})
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    cl = []
    for k, src in sorted(clean.items()):
        p = CLEAN_DIR / f"{k}.sol"
        if not p.exists() or p.read_text(encoding="utf-8", errors="replace") != src:
            p.write_text(src, encoding="utf-8")
        cl.append({"dataset": "solidifi_clean", "path": str(p), "source": src})
    parts = [sb, sf, pd.DataFrame(cl)]
    if with_dappscan:
        parts.append(load_dappscan(labelled_only=True)[["dataset", "path", "source"]])
    df = pd.concat(parts, ignore_index=True)
    df["fid"] = [f"{d}__{re.sub(r'[^A-Za-z0-9_.-]', '_', p)[-150:]}" for d, p in zip(df.dataset, df.path)]
    assert df.fid.is_unique
    return df


# ---------------------------------------------------------------- Slither
def _slither_lines(det: dict, path: str) -> list[int]:
    els = [e for e in det.get("elements", []) if e.get("source_mapping")]
    own = [e for e in els if Path(e["source_mapping"].get("filename_absolute", "")).name == Path(path).name] or els
    nodes = [e for e in own if e.get("type") == "node"]
    el = (nodes or own or [{}])[0]
    return list(el.get("source_mapping", {}).get("lines", []))


def slither_once(path: str, version: str, timeout: int, full: bool = False) -> dict:
    """`full`: keep informational and optimisation detectors (C3 and `slither` exclude them)."""
    solc = ensure_solc(version)
    t0 = time.time()
    excl = [] if full else ["--exclude-informational", "--exclude-optimization"]
    try:
        r = subprocess.run([str(BIN / "slither"), path, "--solc", str(solc), "--json", "-", *excl],
                           capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "seconds": time.time() - t0, "findings": [], "error": ""}
    out = {"seconds": time.time() - t0, "findings": [], "status": "tool_error", "error": ""}
    try:
        js = json.loads(r.stdout)
    except json.JSONDecodeError:
        out["status"] = "compile_error" if _is_compile_failure(r.stderr) else "tool_error"
        out["error"] = _tail(r.stderr) or f"exit code {r.returncode}, no JSON output"
        return out
    if js.get("success"):
        out["status"] = "ok"
        out["findings"] = [{"rule": d["check"], "lines": _slither_lines(d, path), "impact": d.get("impact")}
                           for d in (js.get("results") or {}).get("detectors", [])]
    else:
        err = js.get("error") or ""
        out["status"] = "compile_error" if ("solc" in err.lower() or "compil" in err.lower()
                                            or "Error:" in err) else "tool_error"
        out["error"] = _tail(err) or _tail(r.stderr)
    return out


# ---------------------------------------------------------------- Mythril
def mythril_once(path: str, version: str, timeout: int, exec_timeout: int) -> dict:
    solc = ensure_solc(version)
    t0 = time.time()
    with tempfile.TemporaryDirectory() as d:
        os.symlink(solc, Path(d) / "solc")       # Mythril calls `solc` from PATH
        env = dict(os.environ, PATH=f"{d}:{os.environ['PATH']}")
        try:
            r = subprocess.run([os.environ.get("MYTH", "myth"), "analyze", path, "-o", "json",
                                "--execution-timeout", str(exec_timeout), "--no-onchain-data"],
                               capture_output=True, text=True, timeout=timeout, env=env)
        except subprocess.TimeoutExpired:
            return {"status": "timeout", "seconds": time.time() - t0, "findings": [], "error": ""}
    out = {"seconds": time.time() - t0, "findings": [], "status": "tool_error", "error": ""}
    try:
        js = json.loads(r.stdout)
    except json.JSONDecodeError:
        txt = (r.stdout or "") + (r.stderr or "")
        out["status"] = "compile_error" if re.search(r"Solc|solc|CompilerError|ParserError|Compilation", txt) else "tool_error"
        out["error"] = _tail(txt) or f"exit code {r.returncode}"
        return out
    if js.get("success"):
        out["status"] = "ok"
        out["findings"] = [{"rule": f"SWC-{i.get('swc-id')}", "lines": [i["lineno"]] if i.get("lineno") else [],
                            "impact": i.get("severity"), "title": i.get("title")}
                           for i in js.get("issues", [])]
    else:
        err = str(js.get("error") or "")
        out["status"] = "compile_error" if re.search(r"[Ss]olc|Compil|ParserError|TypeError", err) else "tool_error"
        out["error"] = _tail(err)
    return out


# ---------------------------------------------------------------- SmartCheck
def smartcheck(path: str, timeout: int) -> dict:
    jar = os.environ["SMARTCHECK"]
    cp = jar + (":" + os.path.join(os.environ["JAXB_DIR"], "*") if os.environ.get("JAXB_DIR") else "")
    t0 = time.time()
    try:
        r = subprocess.run(["java", "-cp", cp, "ru.smartdec.smartcheck.app.cli.Tool", "-p", path],
                           capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "seconds": time.time() - t0, "findings": [], "error": ""}
    out = {"seconds": time.time() - t0, "findings": [], "status": "ok", "error": ""}
    for m in re.finditer(r"ruleId: (\S+)\s+patternId: \S+\s+severity: (\d+)\s+line: (\d+)", r.stdout):
        out["findings"].append({"rule": m.group(1), "lines": [int(m.group(3))], "impact": m.group(2)})
    # SmartCheck prints parse problems ("line x:y ...") on stderr and still reports; an exception means no report
    if r.returncode != 0 or "Exception" in r.stderr:
        out["status"] = "tool_error"
        out["error"] = _tail(r.stderr)
    elif re.search(r"^line \d+:\d+ ", r.stderr, re.M):
        out["parse_warnings"] = len(re.findall(r"^line \d+:\d+ ", r.stderr, re.M))
    return out


def run_compiled(tool: str, path: str, src: str, a) -> dict:
    cands, outside = solc_candidates(src)
    if not cands:
        return {"status": "unsupported_pragma", "findings": [], "tried": "", "solc": "", "seconds": 0.0,
                "error": "no known solc release satisfies the pragma", "outside_pragma": outside}
    tried, r = [], {}
    for v in cands:
        r = (slither_once(path, v, a.timeout, full=tool == "slither_full") if tool.startswith("slither")
             else mythril_once(path, v, a.timeout, a.exec_timeout))
        tried.append(f"{v}:{r['status']}")
        r["solc"] = v
        if r["status"] in ("ok", "timeout"):      # a timeout is not retried with an older compiler
            break
    return {**r, "tried": ";".join(tried), "outside_pragma": outside}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="results/contracts")
    ap.add_argument("--resume", default=None, help="existing run folder to continue")
    ap.add_argument("--tools", default="slither,smartcheck,mythril")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--timeout", type=int, default=600, help="wall seconds per tool call")
    ap.add_argument("--exec-timeout", type=int, default=90, help="Mythril --execution-timeout")
    ap.add_argument("--dappscan", action="store_true", help="also SmartCheck on annotated DAppSCAN files")
    a = ap.parse_args()
    run = Path(a.resume) if a.resume else Path(a.out) / time.strftime("v4_%Y%m%d_%H%M%S")
    run.mkdir(parents=True, exist_ok=True)
    df = file_table(a.dappscan)
    df[["fid", "dataset", "path"]].to_csv(run / "files.csv", index=False)
    for v in sorted({v for s in df[df.dataset != "dappscan"].source for v in solc_candidates(s)[0]}):
        for attempt in range(5):                      # GitHub release downloads are rate-limited
            try:
                ensure_solc(v)
                break
            except subprocess.CalledProcessError:
                time.sleep(2 ** (attempt + 1))
        else:
            raise SystemExit(f"cannot download solc {v}")

    jobs = []
    for tool in a.tools.split(","):
        (run / "raw" / tool).mkdir(parents=True, exist_ok=True)
        for r in df.itertuples():
            if tool != "smartcheck" and r.dataset == "dappscan":
                continue
            if not (run / "raw" / tool / f"{r.fid}.json").exists():
                jobs.append((tool, r))
    print(len(jobs), "jobs", flush=True)

    def do(job):
        tool, r = job
        res = smartcheck(r.path, a.timeout) if tool == "smartcheck" else run_compiled(tool, r.path, r.source, a)
        res.update(tool=tool, fid=r.fid, dataset=r.dataset, path=r.path)
        p = run / "raw" / tool / f"{r.fid}.json"
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(res))
        tmp.replace(p)
        return tool, r.fid, res["status"]

    done = 0
    with ThreadPoolExecutor(a.workers) as ex:
        for tool, fid, st in ex.map(do, jobs):
            done += 1
            if done % 25 == 0 or st != "ok":
                print(f"{done}/{len(jobs)} {tool} {fid} {st}", flush=True)

    rows = []
    for p in sorted((run / "raw").glob("*/*.json")):
        d = json.loads(p.read_text())
        rows.append({k: d.get(k) for k in ["tool", "fid", "dataset", "path", "status", "solc", "tried",
                                           "outside_pragma", "seconds", "error"]}
                    | {"n_findings": len(d.get("findings", [])),
                       "rules": ";".join(sorted({f["rule"] for f in d.get("findings", [])}))})
    R = pd.DataFrame(rows)
    R.to_csv(run / "tool_runs.csv", index=False)
    print(R.groupby(["tool", "dataset", "status"]).size().to_string())
    vers = {"slither": subprocess.run([str(BIN / "slither"), "--version"], capture_output=True, text=True).stdout.strip(),
            "mythril": subprocess.run([os.environ.get("MYTH", "myth"), "version"], capture_output=True, text=True).stdout.strip(),
            "smartcheck_jar": os.environ.get("SMARTCHECK", ""),
            "java": subprocess.run(["java", "-version"], capture_output=True, text=True).stderr.strip().splitlines()[-1]}
    write_manifest(run, script=Path(__file__).name, config=vars(a), data_files=list(df.path),
                   extra={"tool_versions": vers})
    print("wrote", run)


if __name__ == "__main__":
    main()
