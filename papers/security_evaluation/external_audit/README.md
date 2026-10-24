# Reproduce the P1.02 candidate metadata audit

`audit_candidate_metadata.py` uses Python 3.9+ and the standard library only. It inspects repository paths, Git blob IDs, byte sizes, source identifiers and contract identifiers. It never parses the CSV `tag` annotations and does not produce training targets or model metrics.

The audit is **within the external candidate only**. It does not establish independence from any development or test corpus in the current study.

## Pinned upstream inputs

- Repository: [Salzano replication package](https://github.com/fsalzano/Empirical-Analysis-of-Vulnerability-Detection-Tools-for-Solidity-Smart-Contracts).
- Branch observed: `main`.
- Commit: `da079440bf2cf4fd803c864ef29aeea8a3da50c3`.
- Root tree: `6c0d44ef03847129939d14cc612fdfc036cb30fc`.
- [Recursive tree JSON](https://api.github.com/repos/fsalzano/Empirical-Analysis-of-Vulnerability-Detection-Tools-for-Solidity-Smart-Contracts/git/trees/6c0d44ef03847129939d14cc612fdfc036cb30fc?recursive=1).
- [Compact manifest CSV](https://raw.githubusercontent.com/fsalzano/Empirical-Analysis-of-Vulnerability-Detection-Tools-for-Solidity-Smart-Contracts/da079440bf2cf4fd803c864ef29aeea8a3da50c3/csvs/sample_of_interest.csv).

Keep downloaded upstream inputs in temporary storage outside Git and the deliverable directory. They are not redistributed with this audit. Preserve CSV bytes and the original filename `sample_of_interest.csv`: the script checks its Git blob ID and size against the tree. Expected SHA-256: `b9e17c5e88188f518491d381b4a2991b5809e8b356e7e861c50e33420d362fb6`; expected size: 199,782 bytes.

## Obtain the inputs

Use a regular GitHub fetch of the two pinned URLs above. For a connector response, save the actual JSON payload for the tree, not the connector envelope containing it. The tree must have a top-level `tree` array and `truncated: false`. Save the CSV as raw UTF-8 bytes; adding a newline or changing line endings changes its Git blob identity.

For example, on a shell with curl:

```bash
mkdir -p /tmp/p1-external-inputs
curl --fail --location 'https://api.github.com/repos/fsalzano/Empirical-Analysis-of-Vulnerability-Detection-Tools-for-Solidity-Smart-Contracts/git/trees/6c0d44ef03847129939d14cc612fdfc036cb30fc?recursive=1' --output /tmp/p1-external-inputs/repo_tree.json
curl --fail --location 'https://raw.githubusercontent.com/fsalzano/Empirical-Analysis-of-Vulnerability-Detection-Tools-for-Solidity-Smart-Contracts/da079440bf2cf4fd803c864ef29aeea8a3da50c3/csvs/sample_of_interest.csv' --output /tmp/p1-external-inputs/sample_of_interest.csv
```

If a local Git checkout already contains the pinned commit, generate the equivalent tree metadata without reading contract contents:

```bash
python - /path/to/upstream-checkout /tmp/p1-external-inputs/repo_tree.json <<'PY'
import json, pathlib, subprocess, sys
repo, output = sys.argv[1:]
commit = 'da079440bf2cf4fd803c864ef29aeea8a3da50c3'
def git(*args):
    return subprocess.check_output(['git', '-C', repo, *args])
entries = []
for record in git('ls-tree', '-r', '-t', '-l', '-z', commit).split(b'\0'):
    if not record:
        continue
    metadata, path = record.split(b'\t', 1)
    mode, kind, sha, size = metadata.decode('ascii').split()
    item = {'path': path.decode('utf-8'), 'mode': mode, 'type': kind, 'sha': sha}
    if size != '-':
        item['size'] = int(size)
    entries.append(item)
tree_sha = git('rev-parse', commit + '^{tree}').decode('ascii').strip()
target = pathlib.Path(output)
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(json.dumps({'sha': tree_sha, 'truncated': False, 'tree': entries}), encoding='utf-8')
(target.parent / 'sample_of_interest.csv').write_bytes(git('show', commit + ':csvs/sample_of_interest.csv'))
PY
```

The JSON serialization may differ between GitHub and local Git. This changes the input JSON file's SHA-256, but the root tree ID and reported object counts remain the comparison keys.

## Run

```bash
python audit_candidate_metadata.py \
  --tree-json /tmp/p1-external-inputs/repo_tree.json \
  --manifest-csv /tmp/p1-external-inputs/sample_of_interest.csv \
  --out P1_02_Metadata_Recount_2026-10-25.json
```

`--out` is an output JSON filename. The four known source-to-directory mappings are declared in `SOURCE_DIRECTORIES`; unrecognized manifest sources are reported, not silently mapped.

## Verified real run

The supplied `P1_02_Metadata_Recount_2026-10-25.json` was produced from the complete pinned GitHub tree and the exact compact manifest bytes:

- 2,182 manifest rows; 2,180 distinct source/contract pairs.
- 2,167 lowercase contract identifiers; 13 appear across source categories.
- 2,181 Solidity files; 2,178 distinct source Git blob IDs.
- Two repeated source/contract keys and three duplicate Git blob groups.
- One ZEUS-vulnerable file has no matching compact-manifest identifier.
- Manifest-to-tree byte verification passed.

The output records the detailed groups and mismatches. Lowercase identifier matching is not address canonicalization. Equal Git blobs establish exact bytes only; no normalization, clone detection, project grouping, label reconciliation or cross-corpus overlap audit is performed. The accompanying note and inventory describe provenance and unresolved licensing separately.
