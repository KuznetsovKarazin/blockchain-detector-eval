"""The downloader must not take an incomplete or wrong checkout for pinned data."""

import importlib.util
import subprocess
from pathlib import Path

_p = Path(__file__).resolve().parents[1] / "scripts" / "00_fetch_data.py"
_spec = importlib.util.spec_from_file_location("fetch", _p)
fetch = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fetch)


def _git(d, *a):
    subprocess.run(["git", "-C", str(d), "-c", "user.email=t@t", "-c", "user.name=t", *a],
                   check=True, capture_output=True)


def test_checkout_state(tmp_path):
    d = tmp_path / "src"
    assert fetch.checkout_state(d, "0" * 40) == "missing"
    d.mkdir()
    assert fetch.checkout_state(d, "0" * 40) == "not_git"
    _git(d, "init", "-q")
    assert fetch.checkout_state(d, "0" * 40) == "incomplete"
    (d / "a.txt").write_text("x")
    _git(d, "add", "a.txt")
    _git(d, "commit", "-qm", "one")
    head = subprocess.run(["git", "-C", str(d), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    assert fetch.checkout_state(d, head) == "pinned"
    assert fetch.checkout_state(d, "0" * 40) == "other_commit"
    (d / "a.txt").write_text("y")
    assert fetch.checkout_state(d, head) == "modified"
    assert fetch.checkout_state(d, "0" * 40) == "other_modified"
