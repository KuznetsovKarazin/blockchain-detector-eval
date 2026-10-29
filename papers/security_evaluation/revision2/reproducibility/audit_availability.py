"""Inspect a public Git tree and private recovery identities; no experiment rerun."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

def sha(data):
    return hashlib.sha256(data).hexdigest()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--repo',type=Path,required=True)
    ap.add_argument('--archive',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args();r=a.repo.resolve()
    commit=subprocess.check_output(['git','-C',str(r),'rev-parse','HEAD'],text=True).strip()
    tracked={x.split('\t',1)[1] for x in subprocess.check_output(['git','-C',str(r),'ls-tree','-r',commit],text=True).splitlines()}
    prefix=r/'papers/security_evaluation/revision1'
    omitted=json.loads((prefix/'publication_omissions.json').read_text())['omitted']
    canonical=json.loads((prefix/'recovery_20261026/representation_edges_v1/manifest.json').read_text())['entries']
    data=a.archive.read_bytes()
    assert len(data)==12907084 and sha(data)=='9bc454eeb4a124145cd847703aa55cf69957e9dea902f9d9427c715e1da7a723'
    originals=[];replacements=[]
    with zipfile.ZipFile(a.archive) as z:
        inventory=json.loads(z.read('BUNDLE_CONTENTS.json'))['files']
        for e in inventory:
            b=z.read(e['path']);assert len(b)==e['bytes'] and sha(b)==e['sha256']
        names=set(z.namelist())
        for e in omitted:
            p=e['path'];record={'path':p,'in_public_commit':p in tracked,'original_path_in_private_archive':p in names}
            if p in names:
                b=z.read(p);h=hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
                record.update(sha256=sha(b),git_blob_sha1=h,matches_original_git_blob=h==e['git_blob_sha'])
                assert record['matches_original_git_blob']
            originals.append(record)
        for e in canonical:
            p=e['new_canonical_path'];b=z.read(p);assert sha(b)==e['new_canonical_npz_sha256']
            replacements.append({'variant':e['variant'],'path':p,'sha256':sha(b),'bytes':len(b),
                                 'in_public_commit':p in tracked,'original_full_unordered_edge_identity_established':False})
    config=json.loads((prefix/'representations/run_20261025_v1/config_before_outputs.json').read_text())
    public_inputs=[]
    for p,h in config['input_hashes'].items():
        b=subprocess.check_output(['git','-C',str(r),'show',f'{commit}:{p}']);assert sha(b)==h
        public_inputs.append({'path':p,'sha256':sha(b),'bytes':len(b),'matches_frozen_hash':True})
    counts={'omitted_original_paths':len(originals),'exact_private_originals':sum(x.get('matches_original_git_blob',False) for x in originals),
            'lost_original_npz':sum(not x['original_path_in_private_archive'] for x in originals),
            'new_canonical_npz':len(replacements),'omitted_or_replacement_binaries_in_public_commit':sum(x['in_public_commit'] for x in originals+replacements),
            'private_bundle_members':len(inventory)+1}
    result={'schema':'article1_r4_availability_audit_v1','public_commit':commit,'method':'Git tree and file identity audit; not a fresh end-to-end rerun',
            'archive_sha256':sha(data),'counts':counts,'original_omissions':originals,'canonical_replacements':replacements,
            'public_representation_input_files':public_inputs,'upstream_pins':config['upstream_pins'],
            'new_fits':0,'new_detector_scans':0,'public_mutations':0}
    a.out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(counts,indent=2))

if __name__=='__main__':main()
