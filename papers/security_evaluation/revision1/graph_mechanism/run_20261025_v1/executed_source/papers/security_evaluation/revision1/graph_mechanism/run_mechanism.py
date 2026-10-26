#!/usr/bin/env python3
"""Predeclared graph-mechanism sensitivities. No model fitting or label validation."""
from __future__ import annotations
import argparse, collections, gzip, hashlib, itertools, json, math, re, shutil, sys, time
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd
import scipy
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'src'))
from bal.data.contracts import load_all, label_files

THRESHOLDS = [.70,.75,.80,.85,.90,.92,.94,.95,.96,.97,.98,.99,1.0]
SEEDS = [1301,1302,1303,1304,1305]
POLICIES = ['project_only','clone_only','joint']
CLASSES = ['reentrancy','unchecked']
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,x): Path(p).write_text(json.dumps(x,indent=2,default=lambda y:y.item() if isinstance(y,np.generic) else str(y))+'\n')
def saveframe(p,df):
    if str(p).endswith('.gz'):
        with open(p,'wb') as f:
            with gzip.GzipFile(filename='',mode='wb',fileobj=f,mtime=0) as z:z.write(df.to_csv(index=False).encode())
    else:df.to_csv(p,index=False)

def group_stars(nodes, selected, field, scope=None):
    """Rebuild within selected nodes: inducing old stars can drop their anchor."""
    q=nodes.loc[selected]
    if scope is not None:q=q[q.scope.eq(scope)]
    q=q[q[field].ne('')]
    left=[];right=[]
    for _,g in q.groupby(field,sort=True):
        ids=sorted(g.node_id)
        left.extend([ids[0]]*(len(ids)-1));right.extend(ids[1:])
    return np.asarray(left,dtype=np.int32),np.asarray(right,dtype=np.int32)

def partition(n, selected, left, right):
    a=coo_matrix((np.ones(len(left),dtype=np.int8),(left,right)),shape=(n,n)).tocsr()
    _, labels=connected_components(a,directed=False)
    canonical=np.full(n,n,dtype=np.int32)
    np.minimum.at(canonical,labels[selected],selected)
    return canonical[labels]

def concentration(labels,ids):
    if not len(ids):return dict(files=0,components=0,giant_files=0,giant_fraction=0.,effective_components=0.)
    sizes=np.unique(labels[ids],return_counts=True)[1]
    return dict(files=len(ids),components=len(sizes),giant_files=int(sizes.max()),giant_fraction=float(sizes.max()/len(ids)),effective_components=float(len(ids)**2/np.dot(sizes.astype(float),sizes)))

def structural_edges(nodes, selected):
    p=group_stars(nodes,selected,'project_id','upstream')
    i=group_stars(nodes,selected,'identifier_key','external')
    r=group_stars(nodes,selected,'file_sha256')
    return tuple(np.concatenate((p[k],i[k])) for k in (0,1)),r

def weighted_cuts(adjacency,weights):
    """Exact DFS cut diagnostics on a simple project-contracted graph.

    Node-removal is a diagnostic, not a proposed change in grouping policy.
    Edge weights are DAppSCAN file counts, not number of arbitrary star links.
    """
    sys.setrecursionlimit(max(10000,len(adjacency)*3))
    disc={};low={};parent={};sub={};separated=collections.defaultdict(list);bridges=[];components=[];clock=0
    def visit(u,verts):
        nonlocal clock
        disc[u]=low[u]=clock;clock+=1;sub[u]=weights[u];verts.append(u)
        for v in sorted(adjacency[u]):
            if v not in disc:
                parent[v]=u;visit(v,verts);sub[u]+=sub[v];low[u]=min(low[u],low[v])
                if low[v]>=disc[u]:separated[u].append(sub[v])
                if low[v]>disc[u]:bridges.append((u,v,sub[v]))
            elif parent.get(u)!=v:low[u]=min(low[u],disc[v])
    for u in sorted(adjacency):
        if u not in disc:
            verts=[];visit(u,verts);components.append((verts,sub[u]))
    total={u:w for vs,w in components for u in vs};arts=[];br=[]
    for u in sorted(adjacency):
        pieces=list(separated[u]);rem=total[u]-weights[u]-sum(pieces)
        if rem>0:pieces.append(rem)
        positive=[x for x in pieces if x>0]
        if len(positive)>1:
            arts.append(dict(vertex=u,component_dapp_files=total[u],removed_project_dapp_files=weights[u],remaining_pieces=len(positive),
                             separated_dapp_files=sum(positive)-max(positive),disconnected_dapp_pairs=(sum(positive)**2-sum(x*x for x in positive))//2))
    for u,v,side in bridges:
        other=total[u]-side
        br.append(dict(left_vertex=u,right_vertex=v,component_dapp_files=total[u],smaller_side_dapp_files=min(side,other),disconnected_dapp_pairs=side*other))
    return arts,br

def contract_projects(nodes,selected,lexical,threshold):
    """Raw-hash equivalence is expanded to a clique of projects, never a star."""
    q=nodes.loc[selected];keys={int(r.node_id):('project:'+r.project_id if r.scope=='upstream' else 'external:'+r.identifier_key) for r in q.itertuples()}
    vertices=sorted(set(keys.values()));vmap={k:i for i,k in enumerate(vertices)};nodev={i:vmap[k] for i,k in keys.items()}
    adj={i:set() for i in range(len(vertices))};weights={i:0 for i in adj};members=collections.defaultdict(list)
    for r in q.itertuples():
        v=nodev[r.node_id];members[v].append(r.node_id);weights[v]+=int(r.dataset=='dappscan')
    links={}
    def add(i,j,kind,score):
        u,v=sorted((nodev[int(i)],nodev[int(j)]))
        if u==v:return
        adj[u].add(v);adj[v].add(u)
        d=links.setdefault((u,v),dict(left_vertex=u,right_vertex=v,lexical_file_pairs=0,raw_hash_groups=0,max_jaccard=0.,example_left_node_id=int(i),example_right_node_id=int(j)))
        if kind=='lexical':
            d['lexical_file_pairs']+=1
            if score>d['max_jaccard']:d.update(max_jaccard=float(score),example_left_node_id=int(i),example_right_node_id=int(j))
        else:d['raw_hash_groups']+=1
    for r in lexical[lexical.jaccard.ge(threshold)].itertuples():add(r.left,r.right,'lexical',r.jaccard)
    for _,g in q.groupby('file_sha256',sort=True):
        representatives={nodev[int(i)]:int(i) for i in g.node_id}
        for i,j in itertools.combinations(representatives.values(),2):add(i,j,'raw',1.)
    return adj,weights,vertices,members,links

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    a.out.mkdir(parents=True,exist_ok=False);start=time.monotonic()
    base=ROOT/'papers/security_evaluation/dependency_audit'
    runs={x:base/f'{x}_recovered_20261025' for x in ['legacy','string_aware']}
    nodes=pd.read_csv(runs['legacy']/'nodes.csv',keep_default_na=False).set_index('node_id',drop=False)
    assert np.array_equal(nodes.index,np.arange(len(nodes)))
    other=pd.read_csv(runs['string_aware']/'nodes.csv',keep_default_na=False)
    assert nodes.path.tolist()==other.path.tolist() and nodes.file_sha256.tolist()==other.file_sha256.tolist()
    bundles=[ROOT/f'papers/security_evaluation/design_feasibility/selected_outside_p90_seed{s}_recovered_v2/selected_memberships.csv.gz' for s in [2,4]]
    inputs=[runs[x]/f for x in runs for f in ['nodes.csv','edges.csv','memberships.csv']]+bundles
    source=Path(__file__);codepaths=[source,source.with_name('test_mechanism.py'),ROOT/'src/bal/data/contracts.py']
    config=dict(schema='revision1_graph_mechanism_v1',started_utc=datetime.now(timezone.utc).isoformat(),thresholds=THRESHOLDS,seeds=SEEDS,
      normalizations=list(runs),policies=POLICIES,source_sha256={str(p.relative_to(ROOT)):sha(p) for p in codepaths},input_sha256={str(p.relative_to(ROOT)):sha(p) for p in inputs},
      label_input_sha256={str(p):sha(ROOT/p) for p in label_files()},
      research_questions={'RQ1':'How do project and clone relations individually and jointly concentrate components as lexical threshold changes?',
        'RQ2':'How does adding files sampled without labels change concentration under a fixed representation and graph rule?',
        'RQ3':'Which project-level articulation vertices and simple cross-project bridges carry transitive connectivity?',
        'RQ4':'For the two already selected development tests, which stated graph definitions retain both proxy classes for training?'},
      population_sampling='SHA256(revision1|seed|path) rank per DAppSCAN source; nested floor(percent*21457/100) prefixes at10..100%; other493 upstream fixed; 5seeds chosen before counts; no label-based sampling',
      historical_selector='Every file with a published SWCsource entry retained; up to20 remaining files/project chosen by Python random.Random(0), sorted-project traversal. This is a label-informed capped historical comparator, not a probability sample.',
      project_only='upstream project groups and within-external equal lowercase identifiers',clone_only='raw-byte equality plus normalized token5gram set Jaccard',joint='union of project_only and clone_only',
      address_edges='omitted; syntactic same-address sensitivity was null in preceding completegraph audit',
      lexical_completeness='reuse exhaustive BLAKE2b128 shingle intersections saved for Jaccard>=.70, then threshold; normalized token collapse is not semantic equivalence',
      contraction='contract upstream project/equal-external-identifier groups; raw-hash equivalence expands to project cliques; lexical cross-project pairs collapse to simple links; no arbitrary group-star articulation interpretation',
      fixed_test='the two postpilot outside_p90_seed2/4 development tests, unchanged1062files; evaluate only cohorts containing them fully, and train only historical6587 DAppSCAN',
      sample_feasibility='structural concentration and whole-largest-component holdout counts on each sampled DAppSCAN population; this is not the fixed1062-file test and not a selected evaluation design',
      limitations=['proxy labels: zero means no published finding, not clean','articulation is project-level diagnostic, not proof a file is a semantic library','no deletion to obtain a desired split','no external model scoring or human label validation','sensitivity analysis motivated by prior results; no confirmatory claims','higher threshold changes dependence definition, does not establish leakage absence'],
      environment=dict(python=sys.version,numpy=np.__version__,pandas=pd.__version__,scipy=scipy.__version__))
    dump(a.out/'config_before_compute.json',config);config_hash=sha(a.out/'config_before_compute.json')
    snap=a.out/'executed_source';snap.mkdir()
    for p in codepaths:
        dst=snap/p.relative_to(ROOT);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dst)
    # All thresholds, seeds, input hashes and executable snapshots exist before outcomes.
    full=load_all(max_unlabelled_per_project=None).set_index('path');label=np.zeros((len(nodes),2),dtype=np.int8)
    up=nodes[nodes.scope.eq('upstream')];label[up.node_id]=full.loc[up.path,CLASSES].to_numpy()
    dapp_ids=nodes.index[nodes.dataset.eq('dappscan')].to_numpy();hist_ids=nodes.index[nodes.historical_train & nodes.dataset.eq('dappscan')].to_numpy()
    assert len(dapp_ids)==21457 and len(hist_ids)==6587
    cohorts={'historical_7080':nodes.index[nodes.historical_train].to_numpy(),'full_dappscan_21457':dapp_ids,
             'full_upstream_21950':up.node_id.to_numpy(),'full_combined_24131':nodes.index.to_numpy()}
    metadata={k:dict(seed=-1,dapp_percent=100. if k!='historical_7080' else len(hist_ids)/len(dapp_ids)*100,selector='historical_cap' if k=='historical_7080' else 'complete') for k in cohorts}
    ranks=[];nondapp=nodes.index[nodes.scope.eq('upstream') & nodes.dataset.ne('dappscan')].to_numpy()
    for seed in SEEDS:
        ranked=sorted(dapp_ids,key=lambda i:hashlib.sha256(f'revision1|{seed}|{nodes.at[i,"path"]}'.encode()).digest())
        ranks.extend(dict(seed=seed,rank=k+1,node_id=int(i)) for k,i in enumerate(ranked))
        for pct in range(10,100,10):
            name=f'hash_seed{seed}_{pct:03d}';cohorts[name]=np.sort(np.concatenate((ranked[:len(ranked)*pct//100],nondapp)))
            metadata[name]=dict(seed=seed,dapp_percent=float(pct),selector='nested_hash_without_labels')
    saveframe(a.out/'population_ranks.csv.gz',pd.DataFrame(ranks))
    tests={}
    for b in bundles:
        m=pd.read_csv(b);t=m[m.role.eq('test')];assert len(t)==1062 and t.path.nunique()==1062
        tests[str(t.test_id.iloc[0])]=nodes.set_index('path').loc[t.path,'node_id'].to_numpy()
    stats=[];feas=[];cuts=[];bridges=[];contractstats=[];edgecounts=[];checks=[];normal_partitions={}
    for normal,run in runs.items():
        e=pd.read_csv(run/'edges.csv');e=e[e.edge_type.eq('normalized_shingle')].copy();assert e.jaccard.ge(.7).all()
        for ci,(cohort,selected) in enumerate(cohorts.items()):
            chosen=np.zeros(len(nodes),dtype=bool);chosen[selected]=True
            sub=e[chosen[e.left.to_numpy()]&chosen[e.right.to_numpy()]]
            prov,raw=structural_edges(nodes,selected);selected_dapp=selected[nodes.loc[selected,'dataset'].eq('dappscan')]
            history=hist_ids[chosen[hist_ids]];member=pd.DataFrame({'node_id':selected});previous={}
            for threshold in THRESHOLDS:
                le=sub[sub.jaccard.ge(threshold)];lex=(le.left.to_numpy(),le.right.to_numpy())
                for policy in POLICIES:
                    pairs=[prov] if policy=='project_only' else ([raw,lex] if policy=='clone_only' else [prov,raw,lex])
                    left=np.concatenate([p[0] for p in pairs]);right=np.concatenate([p[1] for p in pairs])
                    cp=partition(len(nodes),selected,left,right);common=dict(normalization=normal,cohort=cohort,policy=policy,threshold=threshold,**metadata[cohort])
                    if policy in previous:
                        # Raising a threshold may split old components but cannot merge them.
                        q=pd.DataFrame({'new':cp[selected],'old':previous[policy]})
                        assert q.groupby('new').old.nunique().max()==1
                    previous[policy]=cp[selected]
                    cs=concentration(cp,selected_dapp);allcs=concentration(cp,selected)
                    giant=collections.Counter(cp[selected_dapp]).most_common(1)[0][0]
                    train=selected_dapp[cp[selected_dapp]!=giant]
                    row={**common,**cs,'population_files':len(selected),'population_components':allcs['components'],'project_groups_represented':nodes.loc[selected_dapp,'project_id'].nunique(),
                         'largest_component_holdout_train_files':len(train),'largest_component_holdout_test_files':cs['giant_files']}
                    for j,cls in enumerate(CLASSES):
                        pos=int(label[train,j].sum());row[f'holdout_train_{cls}_proxy_positive']=pos;row[f'holdout_train_{cls}_proxy_zero']=len(train)-pos
                        row[f'holdout_train_{cls}_two_proxy_classes']=0<pos<len(train)
                    stats.append(row);edgecounts.append({**common,'structural_star_edges':len(left)-len(lex[0]) if policy!='project_only' else len(left),'lexical_edges':len(lex[0]) if policy!='project_only' else 0})
                    if cohort in ['historical_7080','full_dappscan_21457','full_upstream_21950','full_combined_24131']:
                        member[f'{policy}_{round(threshold*100):03d}']=cp[selected]
                        for test_id,tids in tests.items():
                            assert chosen[tids].all();tc=set(cp[tids]);tr=hist_ids[~np.isin(cp[hist_ids],list(tc))]
                            ts=concentration(cp,tids)
                            for j,cls in enumerate(CLASSES):
                                pos=int(label[tr,j].sum());feas.append({**common,'test_id':test_id,'class':cls,'test_files':len(tids),'test_components':ts['components'],
                                  'largest_test_component_files':ts['giant_files'],'largest_test_component_fraction':ts['giant_fraction'],'raw_train_files':len(tr),
                                  'train_proxy_positive':pos,'train_proxy_zero':len(tr)-pos,'train_components':len(set(cp[tr])),
                                  'positive_train_components':len(set(cp[tr[label[tr,j]==1]])),'two_proxy_classes':0<pos<len(tr)})
                    if cohort=='full_combined_24131' and policy=='joint' and threshold in [.7,.8,.9]:
                        saved=pd.read_csv(run/'memberships.csv')[f'base_{round(threshold*100):03d}'].to_numpy()
                        assert np.array_equal(cp,saved);checks.append(dict(normalization=normal,threshold=threshold,check='saved_complete_graph_reproduced',status='pass'))
                    if policy=='joint' and cohort in ['historical_7080','full_dappscan_21457','full_upstream_21950']:
                        adj,w,verts,vm,links=contract_projects(nodes,selected,sub,threshold)
                        aa,bb=weighted_cuts(adj,w)
                        # Contraction must preserve file-level joint components exactly.
                        vleft=[];vright=[]
                        for u,vs in adj.items():
                            for v in vs:vleft.append(u);vright.append(v)
                        vp=partition(len(verts),np.arange(len(verts)),np.asarray(vleft,dtype=int),np.asarray(vright,dtype=int))
                        mapping=pd.DataFrame([(cp[i],vp[v]) for v,ids in vm.items() for i in ids],columns=['file_component','contracted_component'])
                        assert mapping.groupby('file_component').contracted_component.nunique().max()==1
                        assert mapping.groupby('contracted_component').file_component.nunique().max()==1
                        for r in aa:cuts.append({**common,**r,'project_key':verts[r['vertex']]})
                        for r in bb:
                            edge=links[tuple(sorted((r['left_vertex'],r['right_vertex'])))];bridges.append({**common,**r,**edge,'left_project':verts[r['left_vertex']],'right_project':verts[r['right_vertex']]})
                        contractstats.append({**common,'contracted_vertices':len(verts),'simple_cross_project_edges':len(links),'weighted_articulation_projects':len(aa),'simple_bridges':len(bb),
                                              'max_separated_dapp_files_after_project_removal':max([r['separated_dapp_files'] for r in aa],default=0),
                                              'max_smaller_side_dapp_files_after_simple_bridge_removal':max([r['smaller_side_dapp_files'] for r in bb],default=0)})
                        if threshold==.8:
                            saveframe(a.out/f'contracted_edges_{normal}_{cohort}_080.csv.gz',pd.DataFrame([{**r,'left_project':verts[u],'right_project':verts[v]} for (u,v),r in links.items()]))
                            saveframe(a.out/f'contracted_vertices_{normal}_{cohort}_080.csv',pd.DataFrame([dict(vertex=v,project_key=verts[v],dapp_files=w[v],all_files=len(vm[v]),degree=len(adj[v])) for v in adj]))
            if cohort.startswith(('historical','full_')):
                saveframe(a.out/f'memberships_{normal}_{cohort}.csv.gz',member)
                normal_partitions[normal,cohort]=member
            if ci%10==0:print(f'{normal}: {ci+1}/{len(cohorts)} cohorts',flush=True)
        saveframe(a.out/'component_curves.csv',pd.DataFrame(stats));saveframe(a.out/'fixed_test_feasibility.csv',pd.DataFrame(feas))
    comparisons=[]
    for cohort in list(cohorts)[:4]:
        x=normal_partitions['legacy',cohort];y=normal_partitions['string_aware',cohort]
        for c in x.columns[1:]:comparisons.append(dict(cohort=cohort,partition=c,changed_canonical_memberships=int((x[c]!=y[c]).sum())))
    saveframe(a.out/'normalizer_comparison.csv',pd.DataFrame(comparisons));saveframe(a.out/'edge_counts.csv',pd.DataFrame(edgecounts))
    saveframe(a.out/'articulation_projects.csv',pd.DataFrame(cuts));saveframe(a.out/'bridges.csv',pd.DataFrame(bridges));saveframe(a.out/'contracted_graph_summary.csv',pd.DataFrame(contractstats))
    assert sha(a.out/'config_before_compute.json')==config_hash
    dump(a.out/'summary.json',dict(status='complete_no_model_scores',config_sha256=config_hash,runtime_seconds=time.monotonic()-start,
      graph_outcomes=len(stats),fixed_test_class_outcomes=len(feas),cohorts=len(cohorts),thresholds=len(THRESHOLDS),seeds=SEEDS,
      invariants=dict(saved_graph_reproduction=checks,threshold_refinement='pass',project_contraction_matches_file_partition='pass',stars_regenerated='yes',frozen_config_unchanged=True),
      output_sha256={p.name:sha(p) for p in sorted(a.out.iterdir()) if p.is_file()}))
    print('Complete',time.monotonic()-start,flush=True)
if __name__=='__main__':main()
