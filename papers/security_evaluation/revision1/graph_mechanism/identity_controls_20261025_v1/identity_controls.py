#!/usr/bin/env python3
"""Identity controls separating byte, normalized-stream and shingle-set equality."""
import argparse,hashlib,shutil,time
from pathlib import Path
import numpy as np
import pandas as pd
from run_mechanism import ROOT,sha,dump,saveframe,group_stars,structural_edges,partition,concentration
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();a.out.mkdir(exist_ok=False);start=time.monotonic()
    base=ROOT/'papers/security_evaluation/dependency_audit';runs={n:base/f'{n}_recovered_20261025' for n in ['legacy','string_aware']}
    script=Path(__file__);helper=script.with_name('run_mechanism.py')
    config=dict(schema='identity_graph_controls_v1',source_sha256={p.name:sha(p) for p in [script,helper]},input_sha256={str(r/'nodes.csv'):sha(r/'nodes.csv') for r in runs.values()},
      variants={'project_raw_equality':'project/identifier groups plus rawbyte equality only, no lexical links',
                'project_normalized_stream_nonempty':'project/identifier, rawbyte equality, identical normalized text SHA256 excluding empty normalized streams',
                'project_normalized_stream_with_empty':'same but empty normalized text equality included explicitly'},
      rationale='Jaccard1 is normalized token5gram SET equality, not rawbyte equality or ordered normalized-stream equality; controls do not replace original graph',no_model_scoring=True)
    dump(a.out/'config_before_compute.json',config)
    for p in [script,helper]:shutil.copy2(p,a.out/p.name)
    rows=[];memberrows=[]
    for normal,run in runs.items():
        n=pd.read_csv(run/'nodes.csv',keep_default_na=False).set_index('node_id',drop=False)
        cohorts={'historical_7080':n.index[n.historical_train].to_numpy(),'full_dappscan_21457':n.index[n.dataset.eq('dappscan')].to_numpy(),
          'full_upstream_21950':n.index[n.scope.eq('upstream')].to_numpy(),'full_combined_24131':n.index.to_numpy()}
        for cohort,ids in cohorts.items():
            prov,raw=structural_edges(n,ids);dapp=ids[n.loc[ids,'dataset'].eq('dappscan')];hist=dapp[n.loc[dapp,'historical_train']]
            for variant in config['variants']:
                pairs=[prov,raw]
                if variant!='project_raw_equality':
                    eligible=ids if variant.endswith('with_empty') else ids[n.loc[ids,'normalized_sha256'].ne(hashlib.sha256(b'').hexdigest())]
                    pairs.append(group_stars(n,eligible,'normalized_sha256'))
                cp=partition(len(n),ids,np.concatenate([x[0] for x in pairs]),np.concatenate([x[1] for x in pairs]))
                row=dict(normalization=normal,cohort=cohort,variant=variant,**concentration(cp,dapp))
                row.update({f'historical_projection_{k}':v for k,v in concentration(cp,hist).items()})
                if cohort=='full_combined_24131':
                    tc=set(cp[n.index[n.candidate_test]]);row['external_fixed1998_eligible_historical_dapp_files']=int((~np.isin(cp[hist],list(tc))).sum())
                rows.append(row)
                for i in ids:memberrows.append(dict(normalization=normal,cohort=cohort,variant=variant,node_id=i,component=cp[i]))
    saveframe(a.out/'identity_control_concentration.csv',pd.DataFrame(rows));saveframe(a.out/'memberships.csv.gz',pd.DataFrame(memberrows))
    dump(a.out/'summary.json',dict(status='complete',config_sha256=sha(a.out/'config_before_compute.json'),runtime_seconds=time.monotonic()-start,
      output_sha256={p.name:sha(p) for p in a.out.iterdir() if p.is_file()}))
if __name__=='__main__':main()
