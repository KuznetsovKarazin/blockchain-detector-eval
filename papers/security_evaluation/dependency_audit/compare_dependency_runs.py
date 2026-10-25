#!/usr/bin/env python3
"""Compare frozen normalization graphs without selecting by model outcomes."""
import argparse,json
from pathlib import Path
import pandas as pd
from run_dependency_audit import THRESHOLDS,sha,dump,csvout

def main():
    p=argparse.ArgumentParser();p.add_argument('--legacy',type=Path,required=True);p.add_argument('--corrected',type=Path,required=True)
    p.add_argument('--scanner-audit',type=Path,required=True);p.add_argument('--prior-candidate',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    l=pd.read_csv(a.legacy/'nodes.csv');c=pd.read_csv(a.corrected/'nodes.csv');s=pd.read_csv(a.scanner_audit)
    # Scanner inventory uses repository-root-relative paths; graph metadata keeps
    # candidate paths relative to its pinned upstream repository.
    s['path']=s['path'].str.replace(r'^data/raw/salzano/','',regex=True)
    lm=pd.read_csv(a.legacy/'memberships.csv');cm=pd.read_csv(a.corrected/'memberships.csv')
    assert l.path.equals(c.path) and l.file_sha256.equals(c.file_sha256) and l.candidate_test.equals(c.candidate_test)
    check=l[['path','normalized_sha256']].merge(s[['path','legacy_normalized_sha256']],on='path',validate='one_to_one')
    assert len(check)==24131 and check.normalized_sha256.equals(check.legacy_normalized_sha256)
    check=c[['path','normalized_sha256']].merge(s[['path','corrected_normalized_sha256']],on='path',validate='one_to_one')
    assert check.normalized_sha256.equals(check.corrected_normalized_sha256)
    prior=pd.read_csv(a.prior_candidate);z=lm.merge(prior[['path','proxy_dependency_component_080']],on='path',validate='one_to_one')
    assert len(z)==2181
    assert (z.base_080==z.proxy_dependency_component_080.str.replace('dep_','').astype(int)).all()
    le=pd.read_csv(a.legacy/'edges.csv');ce=pd.read_csv(a.corrected/'edges.csv');rows=[]
    for t in THRESHOLDS:
        x=le[(le.edge_type=='normalized_shingle')&(le.jaccard>=t)];y=ce[(ce.edge_type=='normalized_shingle')&(ce.jaccard>=t)]
        old=set(zip(x.left,x.right));new=set(zip(y.left,y.right))
        for policy in ['base','address_expanded']:
            col=f'{policy}_{int(t*100):03d}';lt=pd.read_csv(a.legacy/f'training_exclusion_{col}.csv');ct=pd.read_csv(a.corrected/f'training_exclusion_{col}.csv')
            assert lt.node_id.equals(ct.node_id)
            rows.append({'grouping':policy,'threshold':t,'legacy_lexical_edges':len(old),'corrected_lexical_edges':len(new),
              'lexical_edges_removed':len(old-new),'lexical_edges_added':len(new-old),
              'nodes_with_changed_canonical_component_representative':int(lm[col].ne(cm[col]).sum()),
              'training_retention_decisions_changed':int(lt.usable_training.ne(ct.usable_training).sum()),
              'legacy_retained_train':int(lt.usable_training.sum()),'corrected_retained_train':int(ct.usable_training.sum())})
    a.out.mkdir(exist_ok=False)
    csvout(a.out/'normalization_graph_comparison.csv',rows)
    group_policy=[]
    for label,m,path in [('legacy',lm,a.legacy),('string_aware',cm,a.corrected)]:
        for t in THRESHOLDS:
            tag=f'{int(t*100):03d}';b=pd.read_csv(path/f'training_exclusion_base_{tag}.csv');e=pd.read_csv(path/f'training_exclusion_address_expanded_{tag}.csv')
            group_policy.append({'normalization':label,'threshold':t,'nodes_with_changed_representative':int(m[f'base_{tag}'].ne(m[f'address_expanded_{tag}']).sum()),
              'train_retention_changes':int(b.usable_training.ne(e.usable_training).sum())})
    csvout(a.out/'address_grouping_comparison.csv',group_policy)
    dump(a.out/'verification.json',{'script_sha256':sha(Path(__file__).read_bytes()),'normalization_stream_changes':int(l.normalized_sha256.ne(c.normalized_sha256).sum()),
      'scanner_audit_stream_hashes_match_all24131':True,'legacy_base_matches_prior_candidate_components_all2181':True,
      'same_raw_population_and_candidate1998':True,'no_model_outcomes_used':True,'rows':rows,'address_policy':group_policy})
    print(json.dumps(rows,indent=2))
if __name__=='__main__':main()
