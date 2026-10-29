"""Separate provenance-only from fixed structural graph denominator controls."""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import csv,hashlib,json
from verify_informative_denominators import ROOT,HERE,REP,read_csv,yes,sha,table_write

def main():
 out=HERE/'structural_baselines_v1';out.mkdir(exist_ok=False)
 inputs=[REP/'nodes_unchanged.csv',REP/'representation_metadata.csv',REP/'structural_edges_unchanged.csv']
 plan={'schema':'r5_structural_denominator_controls_v1','created_utc':datetime.now(timezone.utc).isoformat(),'inputs':{str(p.relative_to(ROOT)):sha(p) for p in inputs},'source_sha256':sha(Path(__file__)),'definitions':{'project_only':'upstream_project + candidate_identifier, matching manuscript project-only definition','fixed_structural_base':'project_only + identical_raw_source, no lexical edges','fixed_structural_address_expanded':'fixed_structural_base + syntactic_address, no lexical edges'},'construction':'All24131unchangednodes; sourceedgesalreadyfrozen; projectionsto21457DAppSCANandfixed15399masked-informativeDAppSCAN','no_models_or_labels':True}
 (out/'PLAN_BEFORE_COMPUTE.json').write_text(json.dumps(plan,indent=2)+'\n')
 nodes,meta,edges=[read_csv(p) for p in inputs];dapp={int(r['node_id']) for r in nodes if r['dataset']=='dappscan'};common={int(r['node_id']) for r in meta if int(r['node_id']) in dapp and yes(r['library_interface_masked_normalized_informative'])};assert len(dapp)==21457 and len(common)==15399
 specs={'project_only':{'upstream_project','candidate_identifier'},'fixed_structural_base':{'upstream_project','candidate_identifier','identical_raw_source'},'fixed_structural_address_expanded':{'upstream_project','candidate_identifier','identical_raw_source','syntactic_address'}}
 rows=[]
 for case,types in specs.items():
  parent=list(range(len(nodes)))
  def find(i):
   while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
   return i
  used=[r for r in edges if r['edge_type'] in types]
  for r in used:parent[find(int(r['left']))]=find(int(r['right']))
  labels=[find(i) for i in range(len(nodes))];allc=Counter(labels[i] for i in dapp);inc=Counter(labels[i] for i in common);fullmax=max(allc.values());allgiants={k for k,v in allc.items() if v==fullmax};inmax=max(inc.values());ingiants={k for k,v in inc.items() if v==inmax};assert len(allgiants)==1 and len(ingiants)==1
  # Independently verify pure project component projections using group identities.
  if case=='project_only':
   byproject=Counter(r['project_id'] for r in nodes if int(r['node_id']) in dapp)
   byprojectinfo=Counter(r['project_id'] for r in nodes if int(r['node_id']) in common)
   assert fullmax==max(byproject.values()) and inmax==max(byprojectinfo.values())
  rows.append({'case':case,'structural_star_edges':len(used),'all_dappscan_denominator':len(dapp),'largest_all_dappscan_component':fullmax,'all_dappscan_fraction':fullmax/len(dapp),'common_informative_denominator':len(common),'largest_common_informative_projection':inmax,'common_informative_fraction':inmax/len(common),'common_nodes_in_all_dappscan_giant':sum(inc[k] for k in allgiants),'same_unique_giant_for_both_projections':allgiants==ingiants})
 table_write(out/'structural_denominators.csv',rows)
 checks={'status':'passed','all_frozen_input_hashes_unchanged':all(sha(ROOT/p)==h for p,h in plan['inputs'].items()),'pure_project_counts_reproduced_by_group_identity':True,'graphs_computed':len(rows),'outputs':{p.name:sha(p) for p in out.iterdir() if p.is_file()}}
 assert checks['all_frozen_input_hashes_unchanged'];(out/'CHECKS.json').write_text(json.dumps(checks,indent=2)+'\n')
 print(json.dumps(rows,indent=2))
if __name__=='__main__':main()
