# P1.02 — Preliminary inventory of the Salzano replication package

**Status: candidate only; independence from the current study has not been verified.**

Audit time: 2026-10-24 23:15:18 UTC (25 October 2026 in Europe/Rome). This is a metadata and provenance audit, not an external model evaluation. No training, predictions, model selection or comparative metrics were performed.

## Pinned source

Repository: [fsalzano/Empirical-Analysis-of-Vulnerability-Detection-Tools-for-Solidity-Smart-Contracts](https://github.com/fsalzano/Empirical-Analysis-of-Vulnerability-Detection-Tools-for-Solidity-Smart-Contracts).

- Default branch: `main`.
- HEAD: `da079440bf2cf4fd803c864ef29aeea8a3da50c3`, dated 25 August 2025.
- Tree: `6c0d44ef03847129939d14cc612fdfc036cb30fc`; recursive API response contains 4,364 entries and is not truncated.
- [Pinned README](https://github.com/fsalzano/Empirical-Analysis-of-Vulnerability-Detection-Tools-for-Solidity-Smart-Contracts/blob/da079440bf2cf4fd803c864ef29aeea8a3da50c3/README.md): 3,411 bytes; Git blob `b0d06778cb1ee16ffa87610d9adbce848fcbb4d8`.
- Article: [An empirical analysis of vulnerability detection tools for solidity smart contracts](https://doi.org/10.1007/s10664-026-10867-7), Empirical Software Engineering 31, 143, published 16 May 2026.

The article reports manual line annotations from three evaluators with review. Its sources are SmartBugs Results, SmartBugs Curated and ZEUS. Tool outputs informed stratified sampling of SmartBugs Results; final annotations were assigned manually. ZEUS source was retrieved through Etherscan addresses. Reported address deduplication within sampling does not establish clone or project independence. The article is CC BY 4.0. These are publication claims, not independently reproduced annotation decisions.

## Counts verified from repository metadata and compact CSVs

| Source | CSV rows | Solidity files | Bytecode files |
|---|---:|---:|---:|
| SmartBugs Results | 1,501 | 1,501 | 1,501 |
| SmartBugs Curated | 143 | 142 | 66 |
| ZEUS safe | 231 | 231 | 231 |
| ZEUS vulnerable | 307 | 307 | 307 |
| **Total** | **2,182** | **2,181** | **2,105** |

`csvs/sample_of_interest.csv` is 199,782 bytes; its SHA-256 is `b9e17c5e88188f518491d381b4a2991b5809e8b356e7e861c50e33420d362fb6`. The without-arithmetic variant is 179,251 bytes; SHA-256 `f27f26437e4220353c528a83e9b6a2a82cdb1c8fba000d7e1a2c874bb23985de`. Both local copies were checked against the repository Git blob IDs. Both contain 2,182 rows and the same source counts. These variants must not be counted as separate observations.

The CSV schema is `label,tag,contract`: `label` identifies the source dataset, `contract` identifies an address or named contract, and `tag` contains `no` or semicolon-separated line/class annotations. A separately inspected curated JSON uses `path`, `lines`, `vulnerability` and `name`. No file-level labels were derived. Their eventual construction requires explicit treatment of missing, unreviewed and out-of-scope classes.

## Identity and consistency findings

The main CSV has **2,180 distinct source/contract pairs**, **2,167 distinct lowercase contract identifiers**, and two repeated source/contract keys. Thirteen lowercase identifiers appear in more than one source category. Lowercasing is an identity-screening step, not a complete Ethereum address or project audit.

The 2,181 Solidity paths contain **2,178 distinct Git blob IDs**. Three pairs of identical blobs occur across the ZEUS safe and vulnerable folders. Those folder names reflect source groupings and cannot be treated as final security labels. The JSON audit records exact paths and IDs.

One ZEUS-vulnerable source file has no corresponding identifier in the compact CSV: `0xdac8da3e58c11b4e0e8dfaefe191107e143ac29b.sol`. The two repeated CSV keys occur in SmartBugs Curated and ZEUS vulnerable. Reconciliation is required before a cohort is frozen.

## Licensing and independence

GitHub reports `license: null`. No file named LICENSE, COPYING or NOTICE is present anywhere in the complete tree, and the README supplies no explicit license. Per-contract SPDX coverage was not inspected. The article's license does not establish a repository-wide license for code, annotation files or third-party contracts; redistribution conditions remain unresolved.

The current project's historical C1 audit already includes SmartBugs. Consequently, the candidate's SmartBugs Curated portion has a clear provenance-overlap risk. No overlap test against current train, validation or previously inspected test files was run. No subset is designated independent.

## Required next steps

1. Resolve license scope and the intended publication snapshot; main predates the 2026 article.
2. Reconcile manifest duplicates, repeated identities and source/manifest mismatches.
3. Compare original and normalized source hashes, bytecode identity, clone groups, deployments and projects against every current development pool.
4. Check line indexing, compiler/dependency information, annotation semantics and source-to-bytecode correspondence.
5. Freeze an eligible residual external cohort, exclusions and evaluation protocol before using external labels to assess models.

Only metadata, two compact manifests and a small label-schema file were retrieved. Full source and with-code CSV datasets were not downloaded. `further_validation.zip` (251,550 bytes) was inventoried but not opened. No remote files were modified. Machine-readable facts and unresolved questions are in `P1_02_External_Candidate_Inventory_2026-10-25.json`.
