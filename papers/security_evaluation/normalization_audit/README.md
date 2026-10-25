# String-aware comment handling sensitivity

This audit changes only comment recognition. Historical Solidity preprocessing
remains unchanged. The corrected scanner respects single and double quotes,
escaped characters, and `hex`/`unicode` string prefixes. Comments become spaces,
preserving CR/LF and character positions. The historical token regex, keyword
set, and identifier/numeral collapse are retained, including their lossy handling
of string contents. This is a lexical sensitivity analysis, not a Solidity parser
or proof of semantic equivalence.

## Recovery and reproducibility

The first completed run's workspace artifacts disappeared before publication.
Source files were reconstructed from their original tool patch text. The scanner
and diagnostic script hashes match independently recorded hashes from that run.
`RECOVERY_EVIDENCE.json` records the previously observed evidence without
pretending to recreate the original configuration or manifest.

`run_recovered_20261025/` is a new execution. Its configuration and source
snapshots were saved before computing normalized streams; `RECOVERY_NOTICE.json`
identifies the reason for the new run. All four raw repositories matched their
pinned commits and were clean. Every one of 24,131 source files was checked
against its recorded SHA-256.

The new full per-file CSV and the 42-case diagnostic CSV match the SHA-256 values
recorded before the disappearance:

| File | SHA-256 |
| --- | --- |
| `source_normalization_audit.csv` | `789053f0213c61cf84efe45520d0944f1baea25d83d8682af41f9e4286956799` |
| `comment_order_diagnostic.csv` | `540dad4c73a59b6cd8f803c070c7857a62699b3ca6cdff7ccb0fab05687f0389` |

The new frozen configuration hash is
`3385102d2431d5867e350802147934c46ee5a8f63bb371e6c4d6dab5bb0e8893`.
The runtime was 42.94 seconds, compared with 37.05 seconds in the earlier
execution. Counts and the available deterministic output digests did not change.
Seventeen scanner tests passed before this execution.

## Source-level results

| Source | Files | Changed normalized streams |
| --- | ---: | ---: |
| Candidate SmartBugs Results | 1,501 | 33 |
| Candidate SmartBugs curated | 142 | 0 |
| Candidate ZEUS safe | 231 | 1 |
| Candidate ZEUS vulnerable | 307 | 1 |
| Reference DAppSCAN, uncapped | 21,457 | 50 |
| Reference SmartBugs curated | 143 | 0 |
| Reference SolidiFI | 350 | 7 |
| **Total** | **24,131** | **92** |

There were zero scanner errors. Fifty changed files contain comment markers
inside quoted literals. For all other 42 changes, the diagnostic locates a
legacy block-regex match starting inside an actual line comment. The historical
block-comment pass precedes line-comment removal; overlapping markers can
therefore leave slash tokens or remove later source text. Recorded examples
contain source identities and line/column pointers, without copying source code.

One DAppSCAN file requires UTF-8 replacement decoding, matching the inherited
loader policy; this is explicitly flagged. No multiline quoted region was found
in this population, although tests cover preserving such input. Preserving a
multiline quoted region does not establish that a compiler would accept it.

## Commands and interface

Run from the repository root with the recorded Python environment and a new
output directory:

```bash
python papers/security_evaluation/normalization_audit/audit_normalization.py prepare --out papers/security_evaluation/normalization_audit/NEW_RUN
python papers/security_evaluation/normalization_audit/audit_normalization.py run --out papers/security_evaluation/normalization_audit/NEW_RUN
python papers/security_evaluation/normalization_audit/diagnose_legacy_comment_order.py --run papers/security_evaluation/normalization_audit/NEW_RUN
python -m pytest tests/test_security_normalization.py -q
```

`solidity_scanner.corrected_normalised_text(source)` returns the corrected stream.
`scan_comments(source)` also returns diagnostics. An unterminated quoted literal
or block comment raises `SolidityScanError`; neither empty text nor legacy text
is substituted. Existing output directories are not overwritten.

This audit reads no vulnerability labels, trains no models, and produces no
external performance scores. Corrected graph results must remain separate from
historical split/pilot results. Lexical graph stability does not establish actual
project or semantic-family independence.
