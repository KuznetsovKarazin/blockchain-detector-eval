#!/usr/bin/env python3
"""Source-reference-only bridge diagnostics and declaration heuristics; no semantic labels."""
import argparse, hashlib, json, re, shutil, sys, time
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'papers/security_evaluation/normalization_audit'))
from solidity_scanner import scan_comments
from run_mechanism import dump,sha,saveframe

def declaration_heuristics(source,path):
    text=scan_comments(source).text
    # Comments are already blank; blank quoted literals before declaration regex.
    text=re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'',lambda m:' '*len(m[0]),text,flags=re.S)
    declarations=re.findall(r'\b(library|interface|contract)\s+([A-Za-z_$][A-Za-z0-9_$]*)',text)
    counts={kind:sum(x==kind for x,_ in declarations) for kind in ['library','interface','contract']}
    stem=Path(path).stem.lower()
    names=['safemath','openzeppelin','erc20','ierc20','safeerc20','ownable','reentrancyguard','address','context','accesscontrol','erc721','ierc721']
    return dict(library_declarations=counts['library'],interface_declarations=counts['interface'],contract_declarations=counts['contract'],
      any_library_or_interface_declaration=bool(counts['library']+counts['interface']),
      exclusively_library_or_interface_declarations=bool(counts['library']+counts['interface']) and counts['contract']==0,
      known_utility_or_standard_filename=any(stem==n or stem.startswith(n+'_') for n in names),
      line_count=len(source.splitlines()),semantic_review='not_reviewed')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();a.out.mkdir(exist_ok=False);start=time.monotonic()
    source=Path(__file__);scanner=ROOT/'papers/security_evaluation/normalization_audit/solidity_scanner.py'
    nodefile=ROOT/'papers/security_evaluation/dependency_audit/legacy_recovered_20261025/nodes.csv'
    inputs=[a.run/x for x in ['component_curves.csv','fixed_test_feasibility.csv','articulation_projects.csv','bridges.csv','contracted_graph_summary.csv']]+[nodefile]
    cfg=dict(schema='graph_mechanism_descriptive_v1',script_sha256=sha(source),scanner_sha256=sha(scanner),input_sha256={str(p):sha(p) for p in inputs},
      scope='metadata-only heuristic source inventory, ranked diagnostic bridge witnesses ; no sources/annotations copied',
      bridge_case_selection='legacy full_dappscan21457 and full_upstream21950, thresholds.8,.95,1: ten links ranked by disconnected DAppSCAN pairs, ties nodeids; retain all support-count metadata',
      caveats=['source declarations and standard filenames are lexical heuristics, not validated semantic roles','a bridge joins projects; exemplar file-pair is one witness, not proof either file is individually necessary','whole-project removal is a mechanism diagnostic, not a proposed filtered graph','descriptive curves, no inferential confidence bands; population ribbons are five seed ranges'])
    dump(a.out/'config_before_describe.json',cfg);shutil.copy2(source,a.out/source.name);shutil.copy2(scanner,a.out/scanner.name)
    nodes=pd.read_csv(nodefile,keep_default_na=False).set_index('node_id',drop=False);rows=[]
    for r in nodes.itertuples():
        p=ROOT/r.path if r.scope=='upstream' else ROOT/'data/raw/salzano'/r.path
        assert sha(p)==r.file_sha256
        h=declaration_heuristics(p.read_text(encoding='utf-8',errors='replace'),r.path)
        rows.append(dict(node_id=r.node_id,dataset=r.dataset,path=r.path,file_sha256=r.file_sha256,**h))
    inventory=pd.DataFrame(rows);saveframe(a.out/'source_declaration_heuristics.csv.gz',inventory)
    bb=pd.read_csv(a.run/'bridges.csv');cases=bb[(bb.normalization=='legacy')&bb.cohort.isin(['full_dappscan_21457','full_upstream_21950'])&bb.threshold.isin([.8,.95,1.])]
    cases=cases.sort_values(['disconnected_dapp_pairs','left_vertex','right_vertex'],ascending=[False,True,True]).groupby(['cohort','threshold'],sort=True).head(10).copy()
    lookup=inventory.set_index('node_id')
    for side in ['left','right']:
        ids=cases[f'example_{side}_node_id'].to_numpy()
        for col in ['path','file_sha256','library_declarations','interface_declarations','contract_declarations','known_utility_or_standard_filename','semantic_review']:
            cases[f'example_{side}_{col}']=lookup.loc[ids,col].to_numpy()
    saveframe(a.out/'ranked_bridge_evidence.csv',cases)
    ag=[]
    populations={'all_dappscan':set(nodes.index[nodes.dataset.eq('dappscan')])}
    for (cohort,threshold),g in bb[bb.normalization.eq('legacy')].groupby(['cohort','threshold']):
        populations[f'bridge_witness_endpoints:{cohort}:{threshold:.2f}']=set(g.example_left_node_id)|set(g.example_right_node_id)
    for name,ids in populations.items():
        d=lookup.loc[sorted(ids)]
        ag.append(dict(population=name,unique_files=len(d),any_library_or_interface_declaration=int(d.any_library_or_interface_declaration.sum()),
          exclusively_library_or_interface_declarations=int(d.exclusively_library_or_interface_declarations.sum()),known_utility_or_standard_filename=int(d.known_utility_or_standard_filename.sum()),
          sampling_interpretation='diagnostic witness set, not probability sample; no semantic-library prevalence claim'))
    saveframe(a.out/'heuristic_aggregate_counts.csv',pd.DataFrame(ag))
    dump(a.out/'summary.json',dict(status='complete_metadata',runtime_seconds=time.monotonic()-start,all24131_raw_source_hashes_verified=True,
      classified_sources=len(inventory),ranked_bridge_cases=len(cases),no_human_semantic_reviews=True,config_sha256=sha(a.out/'config_before_describe.json'),
      output_sha256={p.name:sha(p) for p in a.out.iterdir() if p.is_file()}))
if __name__=='__main__':main()
