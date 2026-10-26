#!/usr/bin/env python3
"""Post-output descriptive tables; no design selection, fitting, or scoring."""
from pathlib import Path
import json
import hashlib
import pandas as pd
from verify_representations import partition_equal

HERE=Path(__file__).resolve().parent
ORIGINAL=HERE/'run_20261025_v1'
CONTROL=HERE/'segmented_control_20261025_v1'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def run():
    primary=[];all_rows=[];inputs={}
    for run_dir in [ORIGINAL,CONTROL]:
        config=json.loads((run_dir/'config_before_outputs.json').read_text())
        inputs[str(run_dir.name)+'/config_before_outputs.json']=sha(run_dir/'config_before_outputs.json')
        for variant in config['variants']:
            folder=run_dir/variant
            concentration=pd.read_csv(folder/'component_concentration.csv')
            training=pd.read_csv(folder/'training_feasibility.csv')
            for metric in ['jaccard','containment']:
                for policy in config['graph_policies']:
                    for threshold in config['thresholds']:
                        c=concentration[(concentration.metric==metric)&(concentration.policy==policy)&(concentration.threshold==threshold)&(concentration.population=='full_dappscan')].iloc[0]
                        t=training[(training.metric==metric)&(training.policy==policy)&(training.threshold==threshold)&(training.training_population=='historical_dappscan')].iloc[0]
                        row={'representation':variant,'metric':metric,'policy':policy,'threshold':threshold,
                             'full_dappscan_files':int(c.files),'full_dappscan_informative':int(c.informative_files),
                             'giant_files':int(c.largest_component_files),'giant_share':c.largest_component_share,
                             'training_before':int(t.before_files),'graph_retained':int(t.retained_by_graph),
                             'informative_retained':int(t.retained_with_informative_representation),
                             'reentrancy_proxy_positive_informative':int(t.reentrancy_proxy_positive_retained),
                             'unchecked_proxy_positive_informative':int(t.unchecked_proxy_positive_retained),
                             'candidate_test_files':int(t.candidate_test_files),'candidate_informative_files':int(t.candidate_informative_files)}
                        all_rows.append(row)
                        if policy=='address_expanded' and threshold==.8:primary.append(row)
            for filename in ['component_concentration.csv','training_feasibility.csv']:
                inputs[str(folder.relative_to(HERE)/filename)]=sha(folder/filename)
    pd.DataFrame(primary).to_csv(HERE/'primary_comparison.csv',index=False)
    pd.DataFrame(all_rows).to_csv(HERE/'all_threshold_comparison.csv',index=False)
    changes=[]
    for suffix in ['normalized','preserved']:
        old=ORIGINAL/('library_interface_masked_'+suffix)/'memberships.csv.gz'
        new=CONTROL/('library_interface_segmented_'+suffix)/'memberships.csv.gz'
        om=pd.read_csv(old);nm=pd.read_csv(new)
        inputs[str(old.relative_to(HERE))]=sha(old);inputs[str(new.relative_to(HERE))]=sha(new)
        for col in om.columns[2:]:
            changes.append({'representation':suffix,'graph':col,'partition_unchanged':partition_equal(om[col],nm[col]),
                            'old_components':om[col].nunique(),'new_components':nm[col].nunique()})
    pd.DataFrame(changes).to_csv(CONTROL/'partition_changes_from_concatenated.csv',index=False)
    diag=pd.read_csv(CONTROL/'boundary_diagnostics.csv');boundary=[]
    inputs[str(CONTROL.name)+'/boundary_diagnostics.csv']=sha(CONTROL/'boundary_diagnostics.csv')
    for name,d in diag.groupby('representation'):
        boundary.append({'representation':name,'nodes':len(d),
                         'files_with_crossing_windows':int((d.boundary_spanning_window_occurrences>0).sum()),
                         'crossing_window_occurrences':int(d.boundary_spanning_window_occurrences.sum()),
                         'files_with_unique_shingles_removed':int((d.boundary_only_unique_shingles_removed>0).sum()),
                         'unique_shingles_removed_sum_per_file':int(d.boundary_only_unique_shingles_removed.sum()),
                         'informative_files':int(d.segmented_informative.sum()),'zero_shingle_files':int((~d.segmented_informative).sum())})
    pd.DataFrame(boundary).to_csv(CONTROL/'boundary_summary.csv',index=False)
    outputs=[HERE/'primary_comparison.csv',HERE/'all_threshold_comparison.csv',CONTROL/'partition_changes_from_concatenated.csv',CONTROL/'boundary_summary.csv']
    (HERE/'comparison_provenance.json').write_text(json.dumps({'status':'post_output_descriptive_summary',
        'script_sha256':sha(Path(__file__)),'input_sha256':inputs,
        'output_sha256':{str(p.relative_to(HERE)):sha(p) for p in outputs}},indent=2)+'\n')
    print(pd.DataFrame(primary).to_string(index=False))

if __name__=='__main__':run()
