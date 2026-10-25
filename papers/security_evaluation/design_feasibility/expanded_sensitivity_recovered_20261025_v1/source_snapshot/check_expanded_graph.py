"""Metadata-only sensitivity of frozen test identities to expanded graphs.

No selection, fitting, score reading or rewriting of frozen bundles. Only joint
exclusions are recalculated; clone-only would need its own new protocol freeze.
"""
from __future__ import annotations
import argparse, hashlib, json, os, shutil, sys
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(Path(__file__).resolve().parent))
import audit_designs as design
dev=design.dev


def check(audit_dir,graph_dirs,bundle_dirs,out):
    if out.exists():raise FileExistsError(out)
    out.mkdir(parents=True)
    audit=json.loads((audit_dir/'design_manifest.json').read_text())
    for name,h in audit['hashes'].items():assert dev.sha256(audit_dir/name)==h,name
    full=dev.load_population()
    for cls,h in audit['proxy_label_hashes_full_order_int8'].items():
        assert hashlib.sha256(full[cls].to_numpy(dtype=np.int8).tobytes()).hexdigest()==h,cls
    inventory=pd.read_csv(audit_dir/'source_inventory.csv')
    for r in inventory.itertuples():assert dev.sha256(ROOT/r.path)==r.file_sha256,r.path
    pop=full[full.dataset=='dappscan'];candidates=pd.read_csv(audit_dir/'candidate_tests.csv')
    old=pd.read_csv(audit_dir/'design_summary.csv').set_index('test_id')
    selected={};bundle_hashes={}
    for b in bundle_dirs:
        manifest=json.loads((b/'design_manifest.json').read_text());name=manifest['membership_file']
        assert dev.sha256(b/name)==manifest['hashes'][name]
        m=pd.read_csv(b/name)
        for tid in m.test_id.unique():selected[tid]=m[m.test_id==tid]
        bundle_hashes[str(b)]=dev.sha256(b/'design_manifest.json')
    assert len(selected)==2
    config={'schema':'expanded_graph_design_sensitivity_v1','created_utc':dev.utc(),
      'source_audit':str(audit_dir),'candidate_test_membership_sha256':dev.sha256(audit_dir/'candidate_tests.csv'),
      'graphs':[str(p) for p in graph_dirs],'bundle_manifest_hashes':bundle_hashes,
      'rule':'Existing T unchanged; exclude all original DAppSCAN training nodes whose fullgraph component intersects T; quarantine scanner-error training nodes',
      'scope':'joint-only sensitivity, no clone-only redesign or score-based selection',
      'screens':'same operational counts/dispersion as design audit, not statistical power',
      'no_models_trained':True,'no_model_scores_read':True,
      'source_sha256':dev.sha256(Path(__file__)),'audit_source_sha256':dev.sha256(Path(design.__file__))}
    dev.dump(out/'config_before_check.json',config)
    snap=out/'source_snapshot';snap.mkdir()
    for p in [Path(__file__),Path(design.__file__)]:shutil.copy2(p,snap/p.name)
    results=[];overlaps=[];links=[];inputs={}
    for graph_dir in graph_dirs:
        names=['nodes.csv','memberships.csv','config_before_graph.json','summary.json']
        inputs[str(graph_dir)]={n:dev.sha256(graph_dir/n) for n in names}
        gs=json.loads((graph_dir/'summary.json').read_text())
        assert gs['nodes']==24131 and gs['no_model_scoring']
        nodes=pd.read_csv(graph_dir/'nodes.csv',keep_default_na=False)
        membership=pd.read_csv(graph_dir/'memberships.csv')
        expanded=membership.merge(nodes[['node_id','file_sha256','normalization_status']],on='node_id',validate='one_to_one')
        upstream=expanded[expanded.scope=='upstream'];assert upstream.path.is_unique
        joined=inventory.merge(upstream,on=['path','dataset'],validate='one_to_one',suffixes=('_original','_expanded'))
        assert len(joined)==7080 and (joined.file_sha256_original==joined.file_sha256_expanded).all()
        g=pop[['file_id','path','reentrancy','unchecked']].merge(joined.drop(columns='dataset'),on=['file_id','path'],validate='one_to_one')
        assert len(g)==6587
        columns=[c for c in membership if c.startswith('base_') or c.startswith('address_expanded_')]
        for col in columns:
            for tid,sub in candidates.groupby('test_id',sort=False):
                test=g[g.file_id.isin(sub.file_id)];assert len(test)==len(sub)
                tc=set(test[col]);other=g[~g.file_id.isin(test.file_id)]
                train=other[(~other[col].isin(tc))&(other.normalization_status=='ok')]
                assert not set(train[col])&tc
                c=design.concentration(test[col])
                row={'graph_normalization':gs['normalization'],'graph_policy_threshold':col,'test_id':tid,
                  'n_test':len(test),'test_components_expanded':len(tc),
                  'test_largest_component_fraction_expanded':c['largest_component_fraction'],
                  'test_inverse_simpson_components_expanded':c['inverse_simpson_component_count'],
                  'expanded_joint_train_n':len(train),'expanded_joint_train_components':int(train[col].nunique()),
                  'expanded_joint_excluded_other_n':len(other)-len(train),
                  'quarantined_other_scan_errors_n':int((other.normalization_status!='ok').sum()),
                  'original_joint_train_n':int(old.loc[tid,'reentrancy_matched_train_n']),'selected_bundle':tid in selected}
                counts=len(train)>=500;disp=c['n_components']>=10 and (c['inverse_simpson_component_count'] or 0)>=5 and (c['largest_component_fraction'] or 0)<=.5;feasible=True
                for cls in design.CLASSES:
                    pt=int(test[cls].sum());pr=int(train[cls].sum());pc=design.concentration(test.loc[test[cls]==1,col])
                    row[f'{cls}_test_positive_proxy']=pt;row[f'{cls}_expanded_joint_train_positive_proxy']=pr
                    row[f'{cls}_positive_test_components_expanded']=pc['n_components']
                    row[f'{cls}_positive_test_inverse_simpson_components_expanded']=pc['inverse_simpson_component_count']
                    counts &= pt>=20 and pr>=20
                    disp &= pc['n_components']>=5 and (pc['inverse_simpson_component_count'] or 0)>=3
                    feasible &= 0<pr<len(train) and 0<pt<len(test)
                row.update(computationally_feasible_both_classes=bool(feasible),count_screen_both_classes=bool(counts),dispersion_screen=bool(disp),joint_count_and_dispersion_screens_pass=bool(feasible and counts and disp))
                results.append(row)
                if tid in selected:
                    m=selected[tid]
                    for (cls,seed,regime),tr in m[m.role=='train'].groupby(['class','seed','regime']):
                        actual=g[g.file_id.isin(tr.file_id)];connected=actual[actual[col].isin(tc)]
                        overlaps.append({'test_id':tid,'graph_normalization':gs['normalization'],'graph_policy_threshold':col,
                          'class':cls,'seed':int(seed),'regime':regime,'original_selected_train_n':len(actual),
                          'expanded_test_connected_train_n':len(connected),'expanded_test_connected_train_positive_proxy':int(connected[cls].sum()),
                          'expanded_test_connected_train_fraction':len(connected)/len(actual),'expanded_joint_component_intersection_n':len(set(actual[col])&tc)})
                    links.extend({'graph_normalization':gs['normalization'],'graph_policy_threshold':col,'test_id':tid,'file_id':int(r.file_id),'expanded_component':int(getattr(r,col))} for r in test.itertuples())
    table=pd.DataFrame(results);table.to_csv(out/'all95_joint_sensitivity.csv',index=False)
    overlap=pd.DataFrame(overlaps);overlap.to_csv(out/'selected_training_overlap.csv',index=False)
    pd.DataFrame(links).to_csv(out/'selected_test_expanded_memberships.csv',index=False)
    primary=table[(table.graph_policy_threshold=='address_expanded_080')&table.selected_bundle]
    strict=overlap[(overlap.graph_policy_threshold=='address_expanded_080')&(overlap.regime=='joint_project_clone_disjoint')]
    fail=not bool(primary.joint_count_and_dispersion_screens_pass.all());connected=bool((strict.expanded_test_connected_train_n>0).any())
    decision={'schema':'expanded_graph_campaign_gate_v1','created_utc':dev.utc(),
      'status':'BLOCKED_EXPANDED_DEPENDENCE' if fail or connected else 'COUNTS_ONLY_PASS_REVIEW_REQUIRED',
      'comparative_training_allowed':False,'external_scoring_allowed':False,'selected_test_ids':list(selected),
      'failed_expanded_operational_screens':fail,'historical_joint_training_intersects_expanded_test_components':connected,
      'reason':'Historical-graph joint exclusions do not establish expanded source-family separation. Preserve frozen bundles as diagnostic provenance; do not score a purported independent campaign.',
      'original_bundle_manifests_unchanged':True,'models_trained':0,'model_scores_read':False,
      'next_condition':'Review expanded graph and redefine/freeze scientific scope or construct valid new manifests without relaxing components',
      'input_hashes':inputs,'selected_bundle_manifest_hashes':bundle_hashes,
      'outputs':{n:dev.sha256(out/n) for n in ['all95_joint_sensitivity.csv','selected_training_overlap.csv','selected_test_expanded_memberships.csv']}}
    dev.dump(out/'CAMPAIGN_GATE.json',decision)
    print(primary.to_string(index=False))
    print(strict.groupby(['graph_normalization','test_id']).expanded_test_connected_train_n.agg(['min','max']).to_string())
    print(table[table.graph_policy_threshold=='address_expanded_080'].groupby('graph_normalization').joint_count_and_dispersion_screens_pass.sum().to_string())
    print(decision['status'])


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--audit',type=Path,required=True)
    p.add_argument('--graphs',type=Path,nargs='+',required=True);p.add_argument('--bundles',type=Path,nargs='+',required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();os.chdir(ROOT);check(a.audit,a.graphs,a.bundles,a.out)


if __name__=='__main__':main()
