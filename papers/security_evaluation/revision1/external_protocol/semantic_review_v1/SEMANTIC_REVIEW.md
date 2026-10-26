# Preliminary Slither mapping review — coordinator only

26 October 2026. **`human_semantic_signoff=false`.** This is a source-level review prepared with AI assistance, not a specialist judgment or a blind reviewer instruction. No target Solidity file, annotation or score was read; no detector was executed. The existing draft mapping is unchanged.

The authoritative implementation here is the installed **Slither 0.11.6** Python source, checked byte-for-byte against the pinned wheel. [source_metadata.json](source_metadata.json) records the wheel/source SHA256 values, metadata assignment lines, method ranges, extractor hash and unchanged protocol hash. Source pointers below are relative to `slither/detectors/` in that installation. The [official detector wiki](https://github.com/crytic/slither/wiki/Detector-Documentation), checked on this date, corroborates the send/transfer warning and gas-price-change rationale; that page is mutable and is not a version pin.

## What the seven selected detectors mean

All seven declare **Medium confidence**. Severity is a tool classification, not proof of an adverse outcome.

| Detector / draft role | Severity | Implemented or documented scope; source pointer |
|---|---|---|
| `reentrancy-eth` / primary | High | Callback and Ether-sending context, with a relevant state variable read before a call and written afterward; additional reentrant-target checks. `reentrancy/reentrancy_eth.py:56–97`. |
| `reentrancy-no-eth` / primary | Medium | Related read-before/write-after test without Ether-sending context. It does not establish an exploitable application outcome. `reentrancy/reentrancy_read_before_write.py:54–92`. |
| `reentrancy-unlimited-gas` / primary | Informational | Its callback predicate accepts **only `Send`/`Transfer`**, despite the potentially misleading name. Findings collect state writes **or events** following a prior recognized call; no read-before-write requirement equivalent to the first two is imposed here. `reentrancy/reentrancy_no_gas.py:58–103`. |
| `reentrancy-benign` / secondary addition | Low | Writes outside the read-before-call set. Documentation describes effects equivalent to two consecutive calls; the detector name does not itself establish harmlessness in every context. `reentrancy/reentrancy_benign.py:31–89`. |
| `reentrancy-events` / secondary addition | Low | Event effects following a call in a reentrant function; documentation discusses event order/value and downstream consumers. `reentrancy/reentrancy_events.py:31–104`. |
| `unchecked-lowlevel` / unchecked | Medium | Tracks low-level returned values; state-variable destinations are skipped, and any IR read removes a tracked value. Consumption is **not** a semantic guarantee of appropriate failure handling. `operations/unchecked_low_level_return_values.py:50–72`. |
| `unchecked-send` / unchecked | Medium | Selects `Send`, inheriting unused-return tracking, including state-variable exclusion and read/tuple consumption rules. `operations/unchecked_send_return_value.py:42–43`; `operations/unused_return_values.py:64–101`. |

The general reentrancy callback test delegates to IR `can_reenter()` (`reentrancy/reentrancy.py:268–279`). These predicates describe analysis machinery; this inspection does not verify every inherited analysis path or soundness/completeness.

`STANDARD_JSON=False` in the five reentrancy detectors controls the result object's `standard_format` (`abstract_detector.py:273–290`). It is **not** a statement that compiler standard-JSON input is unsupported. Compiler applicability and execution coverage require their own checks.

## Decisions required before the B freeze

The current primary union remains `{reentrancy-eth, reentrancy-no-eth, reentrancy-unlimited-gas}`; the broad sensitivity adds `{reentrancy-benign, reentrancy-events}`. Unchecked remains `{unchecked-lowlevel, unchecked-send}`. These are **tool-alert unions**, not yet agreed equivalents of the protocol's expert adverse-outcome classes.

1. Agree the EVM/fork, gas assumptions, callback capabilities and available deployment/import context. In particular, distinguish a send/transfer pattern warning from feasible exploitation under the chosen assumptions; missing decisive context may require `unknown`.
2. Decide whether event-only/off-chain consequences and effects equivalent to repeated ordinary calls satisfy the primary expert outcome. Require an explicit harmful consequence and preconditions, rather than defining truth by a detector identifier or severity.
3. Define adequate unchecked-failure handling: reverting, propagating, recording or intentionally tolerating a failure can have different application consequences. Neither an unused result alone nor a syntactic read establishes that consequence.
4. Agree file-level aggregation, imported-code attribution, failed-analysis handling and the unchanged primary/secondary comparison before viewing scores. Any mapping amendment must state its reason and timing; this note makes none.

The coordinator and named specialists must resolve these choices before human semantic sign-off. Keep this detector-specific note outside the blind probability-review packet; its content must not silently redefine reviewers' answers or supply fabricated sign-off.

## Reproduce the metadata check

From the repository root, using a new output path:

```bash
python papers/security_evaluation/revision1/external_protocol/semantic_review_v1/extract_metadata.py --output /tmp/slither_semantic_metadata_new.json
```

The extractor parses an explicit ten-file Python allowlist as AST and reads the pinned wheel/index and draft protocol. It never imports Slither, opens target corpora or overwrites an existing receipt. The JSON contains metadata and hashes, not copied detector bodies.
