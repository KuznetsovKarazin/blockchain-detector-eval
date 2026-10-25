#!/usr/bin/env python3
"""Report transitive upstream reachability of candidate proxy components.

Uses saved full-population component IDs. It neither filters a final test nor
asserts semantic independence. Source labels are read privately for aggregates.
"""
import argparse
from pathlib import Path
import pandas as pd
from audit_external_sources import sha, write_json

def main():
    p=argparse.ArgumentParser();p.add_argument('--audit',type=Path,required=True);p.add_argument('--private',type=Path,required=True);a=p.parse_args()
    meta=a.audit/'candidate_source_metadata.csv';m=pd.read_csv(meta);labels=pd.read_csv(a.private/'provisional_label_manifest.csv')
    linked=set(m.loc[m.direct_historical_jaccard_ge_080,'proxy_dependency_component_080'])
    repeated=m.contract_id.str.lower().duplicated(keep=False)|m.file_hash.duplicated(keep=False)
    stages={'all_candidate_paths':m,'noncurated':m[m.source_id!='smartbugs_curated'],
      'diagnostic_residual':m[(m.source_id!='smartbugs_curated')&(m.reconciliation=='matched')&~repeated]}
    rows=[]
    for stage,d in stages.items():
        conn=d[d.proxy_dependency_component_080.isin(linked)];all_labels=labels.merge(d[['path','proxy_dependency_component_080']],on='path')
        for c in ['reentrancy','unchecked']:
            positives=all_labels[(all_labels['class']==c)&(all_labels.label_status=='source_reported_positive_pending_adjudication')]
            pc=positives[positives.proxy_dependency_component_080.isin(linked)]
            rows.append({'stage':stage,'class':c,'files':len(d),'directly_connected_files':int(d.direct_historical_jaccard_ge_080.sum()),
              'transitively_connected_files':len(conn),'transitively_connected_proxy_components':conn.proxy_dependency_component_080.nunique(),
              'source_positive_files':len(positives),'source_positive_files_in_connected_components':len(pc),
              'source_positive_connected_components':pc.proxy_dependency_component_080.nunique()})
    out={'schema':'p1_candidate_dependency_reachability_v1','script_sha256':sha(Path(__file__).read_bytes()),'candidate_metadata_sha256':sha(meta.read_bytes()),
      'threshold':.8,'rows':rows,'status':'diagnostic_not_frozen_not_independent',
      'rule':'Mark every candidate component with any direct candidate-to-upstream Jaccard>=0.8 edge, then propagate membership to all candidate files in the component.',
      'next_step':'Derive the full upstream training exclusion manifest from all transitive component memberships, rather than removing only direct neighbors; prefer restricting training before changing the candidate test population.',
      'limitation':'Saved candidate component IDs permit these counts, but full upstream memberships must be exported by the source audit before a training exclusion manifest is frozen. Lexical normalization and project/address provenance limits remain.'}
    write_json(a.audit/'dependency_reachability.json',out)
    print(rows)
if __name__=='__main__':main()
