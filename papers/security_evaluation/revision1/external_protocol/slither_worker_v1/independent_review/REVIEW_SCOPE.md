# Independent Slither worker review scope

Prepared 2026-10-26 before any worker-authored-fixture execution. This document specifies engineering checks; it is not human semantic approval or permission to scan the corpus.

The reviewer will inspect pinned compiler/interpreter/package integrity, loaded-code hashes, fixed source closures, resource limits, private raw-output boundaries, complete detector execution, strict output schemas, exact source attribution, failure-without-score behavior, and the admission/runtime-authorization order. Independent tests will use synthetic dictionaries, temporary files and specifically authored Solidity fixtures only. No raw corpus Slither analysis, external score, label comparison or model fitting is authorized by this review.

The primary mappings remain the draft B unions: reentrancy-eth, reentrancy-no-eth and reentrancy-unlimited-gas; unchecked-lowlevel and unchecked-send. The separate broad sensitivity adds reentrancy-benign and reentrancy-events. Binary alert-union scoring has two score levels and is not a calibrated vulnerability probability. Missing or failed analysis must never receive zero.

The proposed attribution rule uses exactly the first finding element. It must fail on missing, malformed, contradictory or unknown principal source mapping; it must not skip to a convenient later element. Canonical absolute and relative source identities must agree with the frozen closure. Display-only filename_short is not an identity oracle. Other finding elements may concern different source units.

Inherited functions defined in an imported base file may remain import-attributed even when executable through a root-derived contract. Therefore root score zero means no selected root-attributed alert, not a safe deployed contract. This limitation requires an authored inherited-function fixture and remains subject to human semantic sign-off.

Installed Slither 0.11.6 source shows that unchecked-lowlevel detects unused return values, accepts uses/storage that need not adequately handle failure, and that reentrancy-unlimited-gas is Informational and specifically considers send/transfer. An engineering test cannot settle equivalence to the human adverse-outcome definition.

Historical C3 used --exclude-informational, although its nominal map included reentrancy-unlimited-gas. It also retried until Slither success and did not apply this root-first-element attribution. New explicit seven-detector execution, stopping after the first compiler-success, and root attribution are prospective policies, not an exact replay of historical C3. Binary union scoring itself agrees with historical C4's flag scores.

Primary documentation: https://github.com/crytic/slither/wiki/JSON-output. Installed package source and the pinned draft B protocol are the authority for the reviewed implementation. Required concrete tests include inherited/import-only findings, an interface/abstract contract, an early supported compiler, malformed output/container types, path conflict/escape, first-element non-skipping, failed-result empty scores, source/cache tampering, and denial before keys/source reads.
