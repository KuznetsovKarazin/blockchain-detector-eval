"""The 17 prior independent guards plus four exact-byte loader regressions."""
from test_engineering_stage2_orchestration import *  # re-execute unchanged independent cases

import hashlib
import importlib.util
import os
import py_compile
from types import ModuleType


_live_path=BASE/'integrity_preflight.py'
_live=ModuleType('independent_loader_review');_live.__file__=str(_live_path)
sys.modules[_live.__name__]=_live
exec(compile(_live_path.read_bytes(),str(_live_path),'exec'),_live.__dict__)


def test_exact_loader_bypasses_demonstrably_stale_same_time_size_pyc(tmp_path):
    path=tmp_path/'fictional_dependency.py';path.write_text('VALUE = 101\n')
    stat=path.stat();py_compile.compile(str(path),doraise=True)
    path.write_text('VALUE = 202\n');os.utime(path,ns=(stat.st_atime_ns,stat.st_mtime_ns))
    legacy_spec=importlib.util.spec_from_file_location('fictional_stale_oracle',path)
    legacy=importlib.util.module_from_spec(legacy_spec);legacy_spec.loader.exec_module(legacy)
    assert legacy.VALUE==101  # confirms the adversarial bytecode fixture is active
    exact=_live._load_exact_source('fictional_exact_byte_loader',path)
    assert exact.VALUE==202
    assert exact.__source_sha256__==hashlib.sha256(path.read_bytes()).hexdigest()


def test_preloaded_module_object_cannot_replace_current_source(tmp_path):
    path=tmp_path/'fictional_dependency.py';path.write_text('VALUE = 202\n')
    stale=ModuleType('fictional_reused_name');stale.VALUE=101;sys.modules[stale.__name__]=stale
    exact=_live._load_exact_source(stale.__name__,path)
    assert exact is not stale and exact.VALUE==202
    assert sys.modules[stale.__name__] is exact


def test_failed_exact_load_restores_previous_module_cache_entry(tmp_path):
    path=tmp_path/'fictional_dependency.py';path.write_text('raise RuntimeError("fictional failure")\n')
    previous=ModuleType('fictional_failure_restore');sys.modules[previous.__name__]=previous
    with pytest.raises(RuntimeError,match='fictional failure'):
        _live._load_exact_source(previous.__name__,path)
    assert sys.modules[previous.__name__] is previous
    with pytest.raises(RuntimeError):_live._load_exact_source('fictional_no_previous_entry',path)
    assert 'fictional_no_previous_entry' not in sys.modules


def test_actual_trusted_helpers_bind_their_compiled_source_bytes():
    for role,module in [('validate_gate_v2',_live.gate),('review_estimators',_live._review)]:
        expected=hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()
        assert module.__source_sha256__==_live.LIVE_CODE_DIGESTS[role]==expected
    assert _live.analyze_review is _live._review.analyze_review
