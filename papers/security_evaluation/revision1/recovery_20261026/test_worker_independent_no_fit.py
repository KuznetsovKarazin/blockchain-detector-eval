"""Independent synthetic guards only: no classifier fit or corpus operations."""
import os
from pathlib import Path
import py_compile
import sys
import types
import pytest

ROOT=Path(__file__).resolve().parents[4]
SOURCE=ROOT/'papers/security_evaluation/revision1/external_protocol/model_worker_v1/worker.py'


@pytest.fixture
def worker():
    # Load the bytes under review directly, independently of any Python .pyc.
    module=types.ModuleType('independently_reviewed_worker')
    module.__file__=str(SOURCE)
    sys.modules[module.__name__]=module
    exec(compile(SOURCE.read_bytes(),str(SOURCE),'exec'),module.__dict__)
    yield module
    sys.modules.pop(module.__name__,None)


def test_worker_source_drift_blocks_before_orchestration(worker,monkeypatch,tmp_path):
    real=worker.sha
    monkeypatch.setattr(worker,'sha',lambda p:'0'*64 if Path(p)==SOURCE else real(p))
    monkeypatch.setattr(worker,'orchestration',lambda:(_ for _ in ()).throw(AssertionError('admission should not start')))
    with pytest.raises(worker.WorkerError,match='Worker source changed since import'):
        worker.dry_preflight(tmp_path,tmp_path/'binding','0'*64,tmp_path/'release')


def test_unpinned_cached_adapter_is_not_accepted(worker,monkeypatch):
    monkeypatch.setitem(sys.modules,'external_B_worker_adapters',types.ModuleType('untrusted_cached_adapter'))
    assert worker._ADAPTER_LOADED_DIGESTS is None
    with pytest.raises(worker.WorkerError,match='Unpinned cached adapter module'):
        worker.adapters()


def test_same_mtime_same_size_stale_bytecode_is_ignored(worker,tmp_path):
    source=tmp_path/'fictional_probe.py'
    source.write_text('VALUE = 1\n')
    stamp=source.stat()
    py_compile.compile(str(source),doraise=True)
    source.write_text('VALUE = 2\n')
    os.utime(source,ns=(stamp.st_atime_ns,stamp.st_mtime_ns))
    assert source.stat().st_size==stamp.st_size
    try:
        loaded=worker.module('independent_fictional_bytecode_probe',source)
        assert loaded.VALUE==2
    finally:
        sys.modules.pop('independent_fictional_bytecode_probe',None)
