"""
C3  Static-analysis baseline: Slither on the same files as C2.

Research question
-----------------
On the files with trustworthy labels (SmartBugs-curated: manual; SolidiFI:
injected), how does a widely used static analyser score per vulnerability
class, and where does a learned detector have room to add anything?

Mapping of Slither detectors to project classes (fixed in advance):
    reentrancy  reentrancy-eth, reentrancy-no-eth, reentrancy-unlimited-gas,
                reentrancy-benign, reentrancy-events
    timestamp   timestamp
    unchecked   unchecked-lowlevel, unchecked-send
    tx_origin   tx-origin
    arithmetic  (no integer-overflow detector in Slither -> reported as n/a)

Compiler selection: every `pragma solidity` constraint of the file is parsed
(^, ~, >=, >, <=, <, =, ranges); the candidates are the newest allowed release
of each allowed minor version, tried from the newest minor down until Slither
succeeds (e.g. ">=0.4.22 <0.6.0" -> 0.5.17, then 0.4.26). If no release with a
static Linux binary satisfies the pragma (< 0.4.11), the oldest available
release of the same minor is used and flagged `outside_pragma`.

Every file gets a status: ok, compile_error, timeout, tool_error or unsupported_pragma, with the
tried versions and the tail of the error message. Metrics are reported
end-to-end (a failed file counts as "no finding"), conditional on analysed
files, and with coverage. Binary flags also get an AUPRC so that they can be
put next to the AUPRC of learned scores (see c4_slither_vs_ml.py).

Usage
-----
    python scripts/c3_slither_baseline.py --workers 2
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bal.data.contracts import load_smartbugs, load_solidifi   # noqa: E402
from bal.utils.repro import write_manifest                     # noqa: E402

DETECTOR_MAP = {
    "reentrancy": ["reentrancy-eth", "reentrancy-no-eth", "reentrancy-unlimited-gas",
                   "reentrancy-benign", "reentrancy-events"],
    "timestamp": ["timestamp"],
    "unchecked": ["unchecked-lowlevel", "unchecked-send"],
    "tx_origin": ["tx-origin"],
}
LAST_PATCH = {4: 26, 5: 17, 6: 12, 7: 6, 8: 26}
RELEASES = [(0, m, p) for m, last in LAST_PATCH.items() for p in range(last + 1)]
FIRST_STATIC = (0, 4, 11)          # older releases have no static Linux binary
BIN = Path(sys.executable).parent


_VER = r"\d+(?:\.(?:\d+|[xX*]))?(?:\.(?:\d+|[xX*]))?"


def _v(txt: str) -> tuple:
    parts = [int(x) for x in txt.split(".")]
    return tuple(parts + [0] * (3 - len(parts)))


def _partial(txt: str) -> tuple[tuple, int]:
    """Version with wildcards / missing parts filled by 0, and the number of fixed parts."""
    fixed = []
    for x in txt.split("."):
        if not x.isdigit():
            break
        fixed.append(int(x))
    return tuple(fixed + [0] * (3 - len(fixed))), len(fixed)


def _bump(v: tuple, n: int) -> tuple:
    """Smallest version above every version that agrees with v on its first n parts."""
    if n == 0:
        return (10**6, 0, 0)
    w = list(v[:n])
    w[-1] += 1
    return tuple(w + [0] * (3 - n))


def _expand(spec: str) -> list[tuple[str, tuple]]:
    """One `||` alternative as a list of (operator, version) that must all hold.

    Supported (npm-style semver, as used by solc): exact, partial and wildcard
    versions (`0.5`, `0.5.x`, `0.5.*`), comparisons, `^`, `~`, and hyphen
    ranges (`0.4.24 - 0.5.3`).
    """
    hy = re.fullmatch(rf"\s*({_VER})\s+-\s+({_VER})\s*", spec)
    if hy:
        (lo, _), (hi, n) = _partial(hy.group(1)), _partial(hy.group(2))
        return [(">=", lo), ("<=", hi) if n == 3 else ("<", _bump(hi, n))]
    out = []
    for op, ver in re.findall(rf"(\^|~|>=|<=|>|<|=)?\s*({_VER})", spec):
        v, n = _partial(ver)
        if op == "^":
            upper = (0, v[1] + 1, 0) if v[0] == 0 else (v[0] + 1, 0, 0)
            out += [(">=", v), ("<", upper)]
        elif op == "~":
            out += [(">=", v), ("<", _bump(v, min(n, 2)))]
        elif op in ("", "=") and n < 3:
            out += [(">=", v), ("<", _bump(v, n))]
        elif op == ">" and n < 3:
            out.append((">=", _bump(v, n)))
        elif op == "<=" and n < 3:
            out.append(("<", _bump(v, n)))
        else:
            out.append((op or "=", v))
    return out


def _strip_comments(src: str) -> str:
    """Remove // and /* */ comments, so a commented-out pragma is not read."""
    return re.sub(r"/\*.*?\*/|//[^\n]*", " ", src, flags=re.S)


def pragma_constraints(src: str) -> list[list[list[tuple[str, tuple]]]]:
    """For every active `pragma solidity` line, its `||` alternatives, each a list of (operator, version)."""
    return [[_expand(alt) for alt in spec.split("||")]
            for spec in re.findall(r"pragma\s+solidity\s+([^;]+);", _strip_comments(src))]


def allowed(v: tuple, cons) -> bool:
    """Every pragma line must hold; a line holds if any of its alternatives does."""
    ops = {">=": v.__ge__, ">": v.__gt__, "<=": v.__le__, "<": v.__lt__, "=": v.__eq__}
    return all(any(all(ops[op](c) for op, c in alt) for alt in line) for line in cons)


def solc_candidates(src: str) -> tuple[list[str], bool]:
    """Newest allowed release per allowed minor, newest minor first; flag if outside pragma.

    An empty list means that no release known here satisfies the pragma (for
    example `^0.8.28`, newer than the last release in RELEASES): the file is
    reported as `unsupported_pragma` instead of being compiled with a wrong
    version.
    """
    cons = pragma_constraints(src)
    ok = [r for r in RELEASES if allowed(r, cons) and r >= FIRST_STATIC]
    if not ok:
        lo = [r for r in RELEASES if allowed(r, cons)]
        if not lo:
            return [], False
        minor = lo[0][1]
        return [".".join(map(str, next(r for r in RELEASES if r[1] == minor and r >= FIRST_STATIC)))], True
    best = {}
    for r in ok:
        best[r[1]] = max(best.get(r[1], r), r)
    return [".".join(map(str, best[m])) for m in sorted(best, reverse=True)], False


def ensure_solc(version: str) -> Path:
    """Static solc binary from the official GitHub release (cached in ~/.solc-bin)."""
    p = Path.home() / ".solc-bin" / f"solc-{version}"
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        url = f"https://github.com/ethereum/solidity/releases/download/v{version}/solc-static-linux"
        subprocess.run(["curl", "-sSfL", "-o", str(p), url], check=True, timeout=300)
        p.chmod(0o755)
    return p


def run_slither_once(path: str, version: str, timeout: int) -> dict:
    solc = ensure_solc(version)
    t0 = time.time()
    out = {"solc": version, "status": "tool_error", "detectors": [], "error": "",
           "diagnostic_timeout": False}
    try:
        r = subprocess.run([str(BIN / "slither"), path, "--solc", str(solc), "--json", "-",
                            "--exclude-informational", "--exclude-optimization"],
                           capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {**out, "status": "timeout", "seconds": time.time() - t0}
    out["seconds"] = time.time() - t0
    out["returncode"] = r.returncode
    out["stderr"] = r.stderr or ""
    if r.returncode != 0 and not r.stdout.strip() and not out["stderr"].strip():
        # with `--json -` Slither 0.11 prints nothing when it crashes; rerun once for the traceback
        try:
            d = subprocess.run([str(BIN / "slither"), path, "--solc", str(solc)],
                               capture_output=True, text=True, timeout=timeout)
            out["stderr"] = (d.stdout or "") + (d.stderr or "")
        except subprocess.TimeoutExpired:
            out["diagnostic_timeout"] = True
            out["stderr"] = f"diagnostic rerun without --json timed out after {timeout} s"
    try:
        js = json.loads(r.stdout)
    except json.JSONDecodeError:
        if _is_compile_failure(out["stderr"]):
            out["status"] = "compile_error"
        return {**out, "error": _tail(out["stderr"]) or f"exit code {r.returncode}, no JSON output"}
    if js.get("success"):
        out["status"] = "ok"
        out["detectors"] = sorted({d["check"] for d in (js.get("results") or {}).get("detectors", [])})
    else:
        err = js.get("error") or ""
        out["status"] = "compile_error" if ("solc" in err.lower() or "compil" in err.lower()
                                            or "Error:" in err) else "tool_error"
        out["error"] = _tail(err) or _tail(out["stderr"]) or f"exit code {r.returncode}, empty error"
    return out


def _is_compile_failure(text: str) -> bool:
    """solc reported an error (crytic-compile failed) rather than Slither itself crashing."""
    return bool(re.search(r"InvalidCompilation|CompilationError|\.sol:\d+:\d+: (Error|.*Error):", text or ""))


def _tail(text: str | None, n: int = 500) -> str:
    """Last n characters, preferring the last traceback line that names the exception."""
    text = (text or "").strip()
    if not text:
        return ""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    exc = [ln for ln in lines if re.match(r"^\w*(Error|Exception|Failure)\b", ln.strip())]
    tail = text[-n:]
    return (exc[-1].strip() + " | " + tail) if exc and exc[-1] not in tail else tail


def run_slither(path: str, candidates: list[str], timeout: int = 180) -> dict:
    """Try the candidate compilers in order; keep the first success (or the last failure)."""
    if not candidates:
        return {"path": path, "solc": "", "status": "unsupported_pragma", "detectors": [],
                "error": "no known solc release satisfies the pragma", "tried": "", "seconds": 0.0,
                "diagnostic_timeout": False}
    tried = []
    for v in candidates:
        r = run_slither_once(path, v, timeout)
        tried.append(f"{v}:{r['status']}")
        if r["status"] == "ok":
            break
    return {"path": path, **r, "tried": ";".join(tried)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="results/contracts")
    ap.add_argument("--workers", type=int, default=2)
    a = ap.parse_args()
    run = Path(a.out) / time.strftime("c3_%Y%m%d_%H%M%S")
    run.mkdir(parents=True, exist_ok=True)
    df = pd.concat([load_smartbugs(), load_solidifi()], ignore_index=True)
    cand = df.source.map(solc_candidates)
    df["candidates"] = cand.map(lambda c: c[0])
    df["outside_pragma"] = cand.map(lambda c: c[1])
    for v in sorted({v for c in df.candidates for v in c}):
        ensure_solc(v)

    with ThreadPoolExecutor(a.workers) as ex:
        res = list(ex.map(lambda pc: run_slither(*pc), zip(df.path, df.candidates)))
    R = pd.DataFrame(res)
    # full stderr of every file that was not analysed (and of each failed attempt's last try)
    logs = run / "logs"
    logs.mkdir(exist_ok=True)
    for i, row in R[R.status != "ok"].iterrows():
        (logs / f"{Path(row.path).stem}.log").write_text(
            f"path: {row.path}\nsolc: {row.solc}\ntried: {row.tried}\nstatus: {row.status}\n"
            f"returncode: {row.get('returncode')}\ndiagnostic_timeout: {bool(row.get('diagnostic_timeout'))}\n\n"
            f"{row.get('stderr') or ''}")
    R = R.drop(columns=["stderr"], errors="ignore")
    df = df.merge(R, on="path", how="left")
    df["ok"] = df.status == "ok"
    df[["dataset", "path", "solc", "status", "tried", "outside_pragma", "seconds", "diagnostic_timeout", "error"]].assign(
        candidates=df.candidates.map(";".join), detectors=df.detectors.map(";".join)
    ).to_csv(run / "slither_raw.csv", index=False)
    print(df.groupby(["dataset", "status"]).size().to_string())

    rows = []
    for ds, g in df.groupby("dataset"):
        for cls, checks in [*DETECTOR_MAP.items(), ("arithmetic", [])]:
            y = g[cls].to_numpy()
            if y.sum() == 0:
                continue
            flag = g.detectors.map(lambda d: any(c in d for c in checks)).to_numpy()
            ok = g.ok.to_numpy()
            for scope, m in [("end_to_end", np.ones(len(g), bool)), ("analysed_only", ok)]:
                yy, ff = y[m], flag[m]
                tp, fp = int((ff & (yy == 1)).sum()), int((ff & (yy == 0)).sum())
                fn = int((~ff & (yy == 1)).sum())
                rows.append({"dataset": ds, "cls": cls, "scope": scope, "n": int(m.sum()),
                             "n_pos": int(yy.sum()), "coverage": float(ok.mean()),
                             "pos_not_analysed": int((y[~ok] == 1).sum()),
                             "tp": tp, "fp": fp, "fn": fn,
                             "precision": tp / max(1, tp + fp) if checks else np.nan,
                             "recall": tp / max(1, tp + fn) if checks else np.nan,
                             "f1": 2 * tp / max(1, 2 * tp + fp + fn) if checks else np.nan,
                             "auprc_flags": float(average_precision_score(yy, ff)) if checks and yy.sum() else np.nan,
                             "base_rate": float(yy.mean())})
    S = pd.DataFrame(rows)
    S.to_csv(run / "slither_by_class.csv", index=False)
    print(S.round(3).to_string())
    print("not analysed:", int((~df.ok).sum()), "of", len(df))
    write_manifest(run, script=Path(__file__).name, config=vars(a),
                   data_files=list(df.path) + [Path("data/raw/smartbugs-curated/vulnerabilities.json")],
                   extra={"detector_map": DETECTOR_MAP, "slither": subprocess.run(
                       [str(BIN / "slither"), "--version"], capture_output=True, text=True).stdout.strip()})
    print("wrote", run)


if __name__ == "__main__":
    main()
