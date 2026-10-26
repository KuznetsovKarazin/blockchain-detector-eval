"""Run unchanged independent verifiers through explicitly post-result views.

The legacy filename config_before_outputs.json is required by those verifiers.
These view files are not new preregistration: they only redirect private paths
to the fresh recovery outputs and explicitly state their post-result purpose.
"""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
REP = ROOT / 'papers/security_evaluation/revision1/representations'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    recovered = Path(sys.argv[1]).resolve()
    assert recovered.is_relative_to(ROOT / 'data/derived')
    assert json.loads((recovered / 'recovery_result.json').read_text())['status'] == 'complete'
    views = recovered / 'post_result_verification_views'
    views.mkdir(exist_ok=False)
    reports = []
    for kind, oldname, verifier in [
        ('primary', 'run_20261025_v1', 'verify_representations.py'),
        ('segmented', 'segmented_control_20261025_v1', 'verify_segmented_control.py')]:
        original, generated, view = REP / oldname, recovered / kind, views / kind
        view.mkdir()
        config = json.loads((original / 'config_before_outputs.json').read_text())
        config['recovery_view_status'] = 'Post-result verifier input adaptation, not a new scientific freeze'
        config['original_frozen_config_sha256'] = sha(original / 'config_before_outputs.json')
        if kind == 'primary':
            config['private_stream_cache'] = str((recovered / 'streams').relative_to(ROOT))
        else:
            config['private_cache'] = str((recovered / 'segments').relative_to(ROOT))
            config['original_run'] = str((views / 'primary').relative_to(ROOT))
        (view / 'config_before_outputs.json').write_text(json.dumps(config, indent=2)+'\n')
        for path in generated.iterdir():
            if path.name not in ('exact_candidates',):
                (view / path.name).symlink_to(path)
        for name in ('executed_source', 'training_label_input_hashes.json'):
            if not (view / name).exists():
                (view / name).symlink_to(original / name)
        (view / 'manifest.json').write_text(json.dumps({'status':'post_result_recovery_verification_view',
            'fresh_recovery_result_sha256':sha(recovered / 'recovery_result.json'),
            'original_manifest_sha256':sha(original / 'manifest.json')}, indent=2)+'\n')
        script = REP / verifier
        expected = json.loads((original / 'independent_verification.json').read_text())['script_sha256']
        assert sha(script) == expected
        subprocess.run([sys.executable, str(script), '--run', str(view)], cwd=ROOT, check=True)
        report = json.loads((view / 'independent_verification.json').read_text())
        assert report['status'] == 'pass'
        reports.append({'kind':kind, 'unchanged_verifier_sha256':sha(script),
                        'view_config_sha256':sha(view/'config_before_outputs.json'), 'report':report})
    destination = ROOT / 'papers/security_evaluation/revision1/recovery_20261026/REPRESENTATION_INDEPENDENT_CHECK.json'
    assert not destination.exists()
    destination.write_text(json.dumps({'schema':'independent_recomputed_representation_verification_v1',
        'status':'pass', 'wrapper_sha256':sha(__file__), 'reports':reports,
        'original_edge_archive_byte_identity_claimed':False, 'no_model_scoring':True,
        'purpose':'Validate newly recomputed edges, unchanged reported partitions and literal shingles; no original full edge-array comparison is possible'}, indent=2)+'\n')


if __name__ == '__main__':
    main()
