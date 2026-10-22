"""
Source-level representations of Solidity files (C).

No compiler is needed, so every file of every corpus gets a representation
(Solidity versions 0.4-0.8 coexist and many DAppSCAN files do not compile in
isolation).

1. `strip_comments` + `normalise_identifiers` produce a token stream in which
   every user identifier becomes `ID` while keywords, types, global variables
   and member names of the EVM API (`call`, `send`, `transfer`, `delegatecall`,
   `timestamp`, `origin`, ...) are kept. This removes naming artefacts such as
   SolidiFI's `bug_tmstmp12`, while keeping the semantics a detector should use.
2. `pattern_features` computes ~40 counts of expert patterns (normalised per
   100 lines). These are the inputs used for KAN interpretability (Ch. 17):
   each feature has a readable meaning.
3. `near_duplicate_groups` clusters files whose normalised token 5-gram sets
   have Jaccard similarity >= threshold (MinHash LSH), to measure and remove
   cross-split duplication.
"""

from __future__ import annotations

import hashlib
import re
import zlib

import numpy as np
import pandas as pd

KEEP = set("""
pragma solidity contract interface library function modifier event struct enum mapping
returns return if else for while do break continue throw emit new delete
public private internal external view pure payable constant constructor fallback receive
memory storage calldata indexed anonymous virtual override abstract immutable unchecked
require assert revert try catch assembly using is this super selfdestruct suicide
address bool string bytes byte int uint uint8 uint16 uint32 uint64 uint128 uint256 int256 bytes32 bytes4
msg sender value data sig gas gasleft tx origin gasprice block timestamp number difficulty coinbase
gaslimit blockhash now keccak256 sha3 sha256 ecrecover abi encode encodePacked encodeWithSignature
encodeWithSelector decode call send transfer delegatecall staticcall callcode balance
ether wei finney szabo gwei seconds minutes hours days weeks years
true false length push pop
SafeMath add sub mul div mod onlyOwner owner
""".split())

TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|0x[0-9a-fA-F]+|\d+|==|!=|<=|>=|&&|\|\||\+\+|--|\+=|-=|\*=|/=|[{}()\[\];,.=<>+\-*/%!&|^~?:]")


def strip_comments(src: str) -> str:
    src = re.sub(r"/\*.*?\*/", " ", src, flags=re.S)
    src = re.sub(r"//[^\n]*", " ", src)
    return src


def tokens(src: str, normalise: bool = True) -> list[str]:
    toks = TOKEN_RE.findall(strip_comments(src))
    if not normalise:
        return toks
    out = []
    for t in toks:
        if t[0].isalpha() or t[0] == "_":
            out.append(t if t in KEEP else "ID")
        elif t[0].isdigit():
            out.append("NUM")
        else:
            out.append(t)
    return out


def normalised_text(src: str) -> str:
    return " ".join(tokens(src, normalise=True))


def raw_text(src: str) -> str:
    return " ".join(tokens(src, normalise=False))


PATTERNS = {
    # external calls / value transfer
    "call_value": r"\.call\.value\s*\(|\.call\s*\{[^}]*value\s*:",
    "low_level_call": r"\.call\s*[\(\{]",
    "send": r"\.send\s*\(",
    "transfer": r"\.transfer\s*\(",
    "delegatecall": r"\.delegatecall\s*\(",
    "staticcall": r"\.staticcall\s*\(",
    "callcode": r"\.callcode\s*\(",
    # return value handling
    "unchecked_call_stmt": r"^\s*[\w\.\[\]]+\.(call|send|delegatecall)\s*[\(\{][^;]*;\s*$",
    "checked_send": r"(require|assert|if)\s*\(\s*!?\s*[\w\.\[\]]+\.(send|call)",
    # time / randomness
    "block_timestamp": r"\bblock\.timestamp\b",
    "now": r"\bnow\b",
    "block_number": r"\bblock\.number\b",
    "blockhash": r"\bblockhash\s*\(|block\.blockhash",
    "difficulty": r"block\.difficulty|block\.prevrandao",
    "keccak_rand": r"keccak256\s*\(\s*abi\.encodePacked\s*\(\s*(now|block\.)",
    # authorisation
    "tx_origin": r"\btx\.origin\b",
    "tx_origin_eq": r"tx\.origin\s*==|==\s*tx\.origin",
    "msg_sender": r"\bmsg\.sender\b",
    "only_owner": r"\bonlyOwner\b",
    "selfdestruct": r"\b(selfdestruct|suicide)\s*\(",
    # arithmetic
    "plus_eq": r"\+=",
    "minus_eq": r"-=",
    "mul_op": r"[^\*/]\*[^\*/=]",
    "safemath": r"\bSafeMath\b|\.add\s*\(|\.sub\s*\(|\.mul\s*\(",
    "unchecked_block": r"\bunchecked\s*\{",
    # state and control flow
    "require": r"\brequire\s*\(",
    "assert": r"\bassert\s*\(",
    "revert": r"\brevert\s*\(",
    "for_loop": r"\bfor\s*\(",
    "while_loop": r"\bwhile\s*\(",
    "mapping": r"\bmapping\s*\(",
    "payable": r"\bpayable\b",
    "modifier_def": r"\bmodifier\s+\w+",
    "event_emit": r"\bemit\s+\w+",
    "assembly": r"\bassembly\s*\{",
    "balance_read": r"\.balance\b",
    "approve": r"\bapprove\s*\(",
    "transfer_from": r"\btransferFrom\s*\(",
}


def _version(src: str) -> float:
    m = re.search(r"pragma\s+solidity\s*[\^>=<~ ]*\s*(\d+)\.(\d+)", src)
    if not m:
        return np.nan
    return int(m.group(1)) + int(m.group(2)) / 100.0


def call_before_write(src: str) -> int:
    """Crude reentrancy heuristic: an external value call followed, within the
    same function body, by an assignment to a mapping/state element (`x[..] =`,
    `-=`, `+=`). Counted per function."""
    body = strip_comments(src)
    n = 0
    for fn in re.split(r"\bfunction\b", body)[1:]:
        m = re.search(r"\.call\.value\s*\(|\.call\s*\{[^}]*value|\.send\s*\(|\.transfer\s*\(", fn)
        if m and re.search(r"\w+\s*\[[^\]]+\]\s*(=|-=|\+=)", fn[m.end():]):
            n += 1
    return n


PATTERN_NAMES = list(PATTERNS) + ["call_before_write", "solc_version", "pre_08", "loc", "n_functions"]


def pattern_features(src: str) -> dict:
    s = strip_comments(src)
    loc = max(1, sum(1 for line in s.splitlines() if line.strip()))
    f = {}
    for k, rx in PATTERNS.items():
        flags = re.M if k == "unchecked_call_stmt" else 0
        f[k] = 100.0 * len(re.findall(rx, s, flags)) / loc
    f["call_before_write"] = 100.0 * call_before_write(src) / loc
    v = _version(src)
    f["solc_version"] = v if np.isfinite(v) else 0.0
    f["pre_08"] = float(np.isfinite(v) and v < 0.08)
    f["loc"] = float(np.log1p(loc))
    f["n_functions"] = float(np.log1p(len(re.findall(r"\bfunction\b", s))))
    return f


def pattern_matrix(sources) -> pd.DataFrame:
    return pd.DataFrame([pattern_features(s) for s in sources], columns=PATTERN_NAMES)


def exact_hash(src: str) -> str:
    return hashlib.sha1(normalised_text(src).encode()).hexdigest()


def near_duplicate_groups(texts: list[str], threshold: float = 0.8, num_perm: int = 64,
                          ngram: int = 5, seed: int = 0, return_pairs: bool = False):
    """Connected components of the 'Jaccard >= threshold' graph over token n-gram sets.

    1. Identical texts are merged unconditionally (exact hash).
    2. MinHash with banding proposes candidate pairs; EVERY pair inside a bucket is
       verified with the exact Jaccard index (not only pairs with the bucket's first
       member), so the result does not depend on input order.
    Returns a component id per text (the smallest member index), and with
    return_pairs=True also the verified pairs (i, j, jaccard).
    LSH can still miss a pair with Jaccard >= threshold (probabilistic recall);
    `exact_pairs_check` measures that on a corpus.
    """
    rng = np.random.default_rng(seed)
    P = (1 << 61) - 1
    a = rng.integers(1, P, num_perm, dtype=np.uint64)
    b = rng.integers(0, P, num_perm, dtype=np.uint64)
    n = len(texts)
    sets, sigs = [], np.zeros((n, num_perm), dtype=np.uint64)
    for i, t in enumerate(texts):
        toks = t.split()
        # zlib.crc32, not hash(): str hashing is salted per process (PYTHONHASHSEED)
        sh = {zlib.crc32(" ".join(toks[j:j + ngram]).encode()) for j in range(max(1, len(toks) - ngram + 1))}
        sets.append(sh)
        x = np.fromiter(sh, dtype=np.uint64)
        sigs[i] = ((np.outer(a, x) + b[:, None]) % P).min(axis=1) if len(x) else 0
    parent = list(range(n))

    def find(u):
        while parent[u] != u:
            parent[u] = parent[parent[u]]
            u = parent[u]
        return u

    def union(u, v):
        ru, rv = find(u), find(v)
        if ru != rv:
            parent[max(ru, rv)] = min(ru, rv)

    first = {}
    for i, t in enumerate(texts):
        h = hashlib.sha1(t.encode()).hexdigest()
        if h in first:
            union(first[h], i)
        else:
            first[h] = i

    r = 4
    checked, pairs = set(), []
    for bi in range(num_perm // r):
        buckets = {}
        for i in range(n):
            buckets.setdefault(sigs[i, bi * r:(bi + 1) * r].tobytes(), []).append(i)
        for ids in buckets.values():
            for x in range(len(ids)):
                for y in range(x + 1, len(ids)):
                    i, j = ids[x], ids[y]
                    if (i, j) in checked:
                        continue
                    checked.add((i, j))
                    jac = len(sets[i] & sets[j]) / (len(sets[i] | sets[j]) or 1)
                    if jac >= threshold:
                        pairs.append((i, j, jac))
                        union(i, j)
    comp = np.array([find(i) for i in range(n)])
    return (comp, pairs) if return_pairs else comp


def shingle_sets(texts: list[str], ngram: int = 5) -> list[set]:
    out = []
    for t in texts:
        toks = t.split()
        out.append({zlib.crc32(" ".join(toks[j:j + ngram]).encode())
                    for j in range(max(1, len(toks) - ngram + 1))})
    return out


def exact_pairs_check(texts: list[str], threshold: float = 0.8, ngram: int = 5) -> list[tuple]:
    """Brute-force list of all pairs with Jaccard >= threshold (for corpora of a few hundred files)."""
    S = shingle_sets(texts, ngram)
    return [(i, j, len(S[i] & S[j]) / (len(S[i] | S[j]) or 1))
            for i in range(len(S)) for j in range(i + 1, len(S))
            if len(S[i] & S[j]) / (len(S[i] | S[j]) or 1) >= threshold]
