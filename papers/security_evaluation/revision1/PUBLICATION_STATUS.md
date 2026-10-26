# Current publication and recovery status

Updated 26 October 2026. Scientific results, local restoration and public availability are distinct states.

The current manuscript is [DRAFT_REVISION2.md](../manuscript/DRAFT_REVISION2.md), with five tables, six figures, 17 references and explicit AI-assisted-method/declaration text. The Word deliverable is `Article_1_Revision_2_2026-10-26.docx`; all 18 pages passed final visual QA after the availability wording and table/reference-layout fixes; see [the QA receipt](recovery_20261026/MANUSCRIPT_DOCX_QA.json). Revision 1 and its recorded computational results remain preserved.

## What was recovered locally

All four pinned raw repositories and required private annotation/probability-packet inputs are restored and verified. Twenty-three formerly omitted gzip artifacts have been reconstructed **byte-for-byte**, matching the recorded SHA256 and Git blob identities. The [full gzip audit](recovery_20261026/PUBLIC_GZIP_CONTENT_AUDIT.json) inspected every field in 1,083,747 decompressed rows.

The six original lexical-edge NPZ archives were **not** recovered. Six newly computed, independently checked canonical archives exist separately under [representation_edges_v1](recovery_20261026/representation_edges_v1/README.md), with [explicit lineage](recovery_20261026/representation_edges_v1/manifest.json). All 120 reported component partitions and 20 surviving result CSVs agree with the original evidence. This does not prove identity of the complete original unordered edge lists. Original NPZ hashes/paths are not silently replaced. A separate [canonical NPZ schema/content audit](recovery_20261026/CANONICAL_NPZ_SCHEMA_AUDIT.md) checked all 24 arrays, 4,621,780 edge rows and all 6,357,241 archive bytes. It does not establish lost-original identity or publication permission. See [representation recovery](recovery_20261026/REPRESENTATION_RECOVERY.md).

The historical [publication_omissions.json](publication_omissions.json) remains unchanged as the original 29-path checkpoint. It is not the current local missing-file inventory.

## What the public update includes

Automatic publication review again rejected public upload of the compressed graph artifacts after the full content audit. The current update therefore includes new source code, reports and textual metadata only; it excludes the 23 recovered gzip files and six new NPZ files. No further public retry, alternative encoding or alternative public delivery is being attempted. Public deposit of the complete compressed graph package remains pending.

A verified 42-file recovery bundle (12,907,084 bytes; SHA256 `9bc454eeb4a124145cd847703aa55cf69957e9dea902f9d9427c715e1da7a723`) is designated for separate private delivery to the user, not public publication. Its [receipt](recovery_20261026/PRIVATE_BUNDLE_RECEIPT.json) identifies the package. The bundle was successfully saved privately for the author. The final Word manuscript was also successfully saved privately. Private storage identifiers are not published here. Raw third-party sources, original row annotations, reviewer keys and private contractual material remain excluded from the public update.

## External study status

The fixed B cohort and private blank-review package are restored. [Current engineering readiness](external_protocol/ENGINEERING_READINESS_20261026.md) records 24 adapter tests, 24 performance tests, 21 independent checks and the separate toolchain verification. [The final verification](recovery_20261026/FINAL_VERIFICATION_20261026.json) records 251 unique passing tests (237 main + 14 toolchain). These are scoped implementation checks; actual human judgments, external model fits/scores, contract compilation and Slither scans are zero. The overall protocol and B draft remain unfrozen; genuine human review, semantic sign-off and authenticated execution integration are still required.

The earlier graph and model analyses are development evidence: 3,822 graph outcomes and 360 logical historical-test evaluations / 282 physical fits. Recovery did not add model fits or independent external test results. No new DOI, journal submission or third-party correspondence was performed.
