# External source audit on 25 October 2026

The external candidate has not been accepted as an independent test. This run
reconciles source identities, records provisional annotation status, and screens
lexical dependencies before any model scoring. It uses the pinned Salzano
commit `da079440bf2cf4fd803c864ef29aeea8a3da50c3` and all original files in the
three pinned reference corpora: 21,457 DAppSCAN, 350 SolidiFI and 143 SmartBugs.

## What was established

There are 2,182 manifest rows, 2,180 source/identifier keys and 2,181 source
paths. Seventeen paths require source reconciliation: fourteen have annotation
line numbers greater than the saved source line count, two have repeated keys
with different annotations, and one has no manifest record. None of the
annotations uses line zero. Ordinary inspected annotations agree with 1-based
line indexing; the high line numbers remain source/location inconsistencies,
not automatically disproved vulnerability labels.

The two repeated keys require different resolutions. The curated key
`0x627fa62ccbb1c1b04ffaecd72a53e37fc0e17839` has two classes whose locations
plausibly refer to the same file. The ZEUS-vulnerable key
`0x9220d625bd6bea95c865b3c4faf273bfbd6bc48a` has a second row whose timestamp
location 107 and unchecked-call locations 114/118 match the otherwise unmatched
source `0xDAC8da3e58c11B4e0E8DFaeFe191107e143AC29B.sol`, rather than the named
source. This is evidence of a possible identifier transcription error. The
adapter quarantines both identities; it does not silently reassign the row.

The source's `no` and `no;` markers are normalized consistently. The taxonomy
maps `unchecked_low_calls` to the study class `unchecked`. Positives, explicit
no-finding annotations, absence of the selected class in a nonempty annotation,
and unresolved identity/location are separate statuses. Every binary target
remains blank at this stage. The upstream first-match-by-contract evaluation
logic is not reused because it ignores source identity and repeated records.

## Dependency screening

The exhaustive lexical screen covered 24,131 files, including all 2,181
candidate paths. It uses normalized token 5-gram sets, exact sparse intersection
counts, and fixed Jaccard thresholds 0.7, 0.8 and 0.9. It does not use an LSH
candidate step. Tokens are represented by 128-bit shingle digests; the exactness
claim applies to that representation. Direct source hashes are separate.

| Check against all reference sources | Candidate paths | Beyond the curated source |
| --- | ---: | ---: |
| Equal raw source bytes | 142 | 0 |
| Equal normalized token stream | 148 | 6 |
| Jaccard at least 0.8 | 208 | 66 |

At thresholds 0.7 and 0.9, the direct-overlap counts are respectively 328 and
166 candidate paths. Project membership within the reference sources,
candidate repeated identifiers, and lexical clone edges are joined transitively
over the full population. At threshold 0.8, candidate paths occupy 1,113 proxy
components. These are dependency proxies, not verified real-world project or
deployment families. Their numbers must not be called independent sample sizes.

Legacy output fields containing `historical` or `sample` refer to this full
uncapped reference corpus in this run; `upstream_scope` records that explicitly.
Some reference files were never fitted in the historical capped experiments.

## Diagnostic cohort flow

| Diagnostic stage | Files | Reentrancy source positives | Unchecked source positives |
| --- | ---: | ---: | ---: |
| Exclude previously used curated source | 2,039 | 47 | 208 |
| Quarantine source reconciliation issues | 2,023 | 47 | 208 |
| Also quarantine repeated identities | 1,998 | 46 | 200 |

The last row covers 91.61% of candidate source paths and contains 43 and 129
positive proxy components respectively. Five files still have a normalized
match and 65 a direct Jaccard-at-least-0.8 relation with reference sources.
Transitive reachability is broader: **186 of these 1,998 files, in 11 proxy
components, remain connected to upstream data**. They include five of the 46
source-reported reentrancy positives (four components) and two of the 200
unchecked positives (two components). Across all candidate paths the analogous
count is 329 files in 108 connected components, versus 208 directly linked files.
See `source_audit_full_20261025/dependency_reachability.json`.
These are diagnostic counts, not an adopted exclusion policy or final test.
The preferred next response to a test/training overlap is to restrict training
where feasible; further test exclusions require an explicit population change.
The complete upstream membership of these transitive components must still be
exported and used to construct a training exclusion manifest. Removing only the
65 direct neighbors would be insufficient. No such training manifest has yet
been frozen, and the remaining 995 proxy components are not 995 established
independent real-world families.

Repeated valid-looking addresses are not automatically one verified deployment:
network and retrieval provenance remain unresolved. Equal normalized code does
not establish source identity, and is not used as identity deduplication.

## Review packet and remaining limits

The generated reference packet contains 106 file-class cases from 83 files and
25 proxy components: 50 reentrancy and 56 unchecked. The second assessor has
51 initial cases, including all selected source-reconciliation disputes and a
random quarter of the others. Human reviews completed: zero. The first sample
is purposeful diagnostic sampling; no population error rate or sampling weight
is claimed. See `LABEL_REVIEW_PROTOCOL.md` and the blank CSVs under
`source_audit_full_20261025/review_packet/`. The source-label key remains private.

The packet is blind to model scores. Upstream path names reveal source category,
and source comments may reveal original annotations; it is not fully blinded
to provenance or original labels.

The legacy normalizer deliberately collapses identifiers and numeric literals.
Its regex comment removal can also strip comment-like text inside Solidity
string literals. Therefore these lexical groups need a string-aware sensitivity
check and sampled edge inspection before protocol freeze. Exact all-pairs
screening removes LSH retrieval uncertainty, not normalization error or missing
business-project metadata. Compiler/dependency semantics are not certified.

No SPDX identifiers were observed in the candidate source files. This does not
establish legal status; redistribution permissions remain unresolved. Raw code
and row-level upstream annotations are not included in the tracked audit.

## Reproduction and verification

From the repository root, after fetching all pinned sources and the pinned
candidate into `data/raw/salzano`, use fresh output directories:

```bash
python papers/security_evaluation/external_audit/audit_external_sources.py \
  --full-upstream \
  --out papers/security_evaluation/external_audit/source_audit_reproduction \
  --private-out data/derived/security_external_reproduction
python papers/security_evaluation/external_audit/finalize_external_audit.py \
  --audit papers/security_evaluation/external_audit/source_audit_reproduction \
  --private data/derived/security_external_reproduction
python papers/security_evaluation/external_audit/summarize_dependency_reachability.py \
  --audit papers/security_evaluation/external_audit/source_audit_reproduction \
  --private data/derived/security_external_reproduction
```

The recorded run took 88.54 seconds with a maximum resident size of 628,592 KiB
(approximately 614 MiB) in this environment. The postcheck separately verified
100 retained overlap edges using literal tuple shingles, checked that all raw
and normalized equality pairs occur among the screened edges, verified source
path counts, and checked all four upstream checkouts were clean at their pins.
It exports hashes and metadata for every one of the 21,950 reference files.
Executed script/import snapshots and their hashes are preserved alongside the
result. Run the original paths above; the snapshots are evidence copies, not
standalone relocated entry points.

An earlier historical-subset attempt failed only when serializing a NumPy
integer in the summary. Its partial files and log were preserved locally under
`data/derived/`; they are not used for the reported numbers. No external
predictions, model selection or comparative performance evaluation occurred.
