"""Independent replay of new ordered-equality graphs and fixed-control checks."""
from pathlib import Path
import hashlib,json,subprocess,sys
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3]
REP=ROOT/'papers/security_evaluation/revision1/representations/run_20261025_v1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 out=HERE/'trivia_run_20261028_v1';n=pd.read_csv(REP/'nodes_unchanged.csv',keep_default_na=False).query("dataset=='dappscan'").reset_index(drop=True);h=pd.read_csv(out/'source_verified_canonical_hashes.csv',keep_default_na=False);m=pd.read_csv(out/'memberships.csv.gz');assert np.array_equal(n.node_id,h.node_id) and np.array_equal(n.node_id,m.node_id)
 cols=['project_raw','project_raw_trivia_only_nonempty','project_raw_old_preserved_nonempty','project_raw_normalized_nonempty']
 # Refinement on every file, not merely matching aggregate giant sizes.
 checks=[]
 for small,large in zip(cols,cols[1:]):
  assert m.groupby(small)[large].nunique().max()==1;checks.append(f'{small} refines {large}')
 parent=list(range(len(n)))
 def find(i):
  while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
  return i
 def merge_group(values):
  groups={}
  for i,v in enumerate(values):
   if not v:continue
   if v in groups:parent[find(i)]=find(groups[v])
   else:groups[v]=i
 merge_group(n.project_id);merge_group(n.file_sha256);merge_group(h.trivia_tokens_sha256.where(h.informative,''))
 rebuilt=np.array([find(i) for i in range(len(n))]);df=pd.DataFrame({'rebuilt':rebuilt,'saved':m.project_raw_trivia_only_nonempty})
 assert df.groupby('rebuilt').saved.nunique().max()==1 and df.groupby('saved').rebuilt.nunique().max()==1
 p=HERE/'test_trivia_only.py';test=subprocess.run([sys.executable,'-m','pytest','-q',str(p)],capture_output=True,text=True);assert test.returncode==0;assert '23 passed' in test.stdout
 (out/'SCANNER_TESTS.txt').write_text(test.stdout+test.stderr)
 info={'status':'passed','checked_rows':len(n),'independent_union_find_graphs':1,'partition_refinement_checks':checks,'scanner_tests':23,'test_source_sha256':sha(p),'test_stdout_sha256':sha(out/'SCANNER_TESTS.txt'),'verified_result_sha256':sha(out/'RESULT.json'),'verifier_source_sha256':sha(Path(__file__))}
 (out/'INDEPENDENT_CHECK.json').write_text(json.dumps(info,indent=2)+'\n');print(json.dumps(info,indent=2))
if __name__=='__main__':main()
