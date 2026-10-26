"""Read-only fail-closed guard; never performs an external model operation."""
import argparse,hashlib,json
from pathlib import Path

def blockers(protocol,base,phase):
    bad=[]
    for name,want in protocol.get('hashes',{}).items():
        path=base/name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=want:bad.append('hash:'+name)
    bad.extend('freeze:'+k for k,v in protocol.get('freeze_prerequisites',{}).items() if v is not True)
    for key in ['reviewer_1_name','reviewer_2_name']:
        if not protocol.get('probability_audit',{}).get(key):bad.append('missing:'+key)
    if protocol.get('status')!='frozen_before_human_judgments_and_scores':bad.append('protocol_not_prospectively_frozen')
    if phase=='score':bad.extend('score:'+k for k,v in protocol.get('score_prerequisites',{}).items() if v is not True)
    return sorted(set(bad))

def main():
    p=argparse.ArgumentParser();p.add_argument('--protocol',type=Path,required=True);p.add_argument('--phase',choices=['begin-review','score'],default='score');a=p.parse_args()
    data=json.loads(a.protocol.read_text());bad=blockers(data,a.protocol.parent,a.phase)
    print(json.dumps({'phase':a.phase,'allowed':not bad,'blockers':bad,'models_executed':0},indent=2))
    raise SystemExit(2 if bad else 0)
if __name__=='__main__':main()
