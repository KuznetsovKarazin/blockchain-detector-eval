# B feature adapters, version 1

This directory completes the representation-adapter proposal for the four methods in the existing B draft. It does not freeze or alter that draft, authorize external scoring, establish semantic class mappings, or supply human assessments. All fitting tests use synthetic strings. Real files are used only for read-only preprocessing and hash/coverage checks.

## API and fitted-state boundary

`SourceRecord(sample_id, role, source)` requires a unique string identity, an explicit `train` or `external` role and source bytes/text. `load_verified_records` in `check_coverage.py` constructs these records from the fixed public 691-training and 1,998-external manifests, checking membership, component exclusion, source byte hashes and identities. The coverage command also verifies the four pinned clean upstream repositories. No private annotation key, proxy label, human response or model score is opened.

`adapter_for_method` returns the following unfitted objects:

| Declared B method | Representation adapter | Fitted preprocessing |
|---|---|---|
| `raw_tfidf_lr` | `TrainOnlyTfidf('raw')` | Training-only vocabulary/IDF, then sparse StandardScaler |
| `normalized_tfidf_lr` | `TrainOnlyTfidf('normalized')` | Training-only vocabulary/IDF, then sparse StandardScaler |
| `pattern_rf` | `Pattern43()` | None; fixed 43 float32 features |
| `pattern_lgbm` | `Pattern43()` | None; same fixed 43 features |

For TF-IDF, `fit_transform_training` accepts only training-role records and permits one successful fit per object. Pattern43 exposes the same training entrypoint as a strict cohort-validation/extraction wrapper, without fitting parameters. Any invalid training input or unusable training vocabulary aborts; it never silently excludes a training row. `transform` checks that external identities do not overlap training identities and applies only the saved vocabulary/IDF/scaler. A digest covers training IDs/source hashes, vocabulary, IDF and all scaler arrays; each transform verifies that this state is unchanged. Transforming a train-role record also requires its identity and source hash to match the fitted training provenance. Source-role checks cannot prevent a caller from deliberately mislabelling an external file as training, so the verified manifest loader is part of the input contract.

The lexical settings are the historical token regex, whitespace-token TF-IDF with 1–3 grams, min_df=2, max_features=50,000, sublinear_tf=True and lowercase=False, followed by StandardScaler(with_mean=False). `adapter_plan.json` records every effective sklearn preprocessing parameter, package version and the unchanged four model configurations from the B draft. No classifier is created or fitted by this adapter module. Model configuration inclusion records the proposal; it is not an execution permission.

## Exact lexical and pattern definitions

`feature_definitions.json` records all 43 names, exact regular expressions/order, normalizers, summary formulas, token regex and normalization KEEP set. Both lexical representations invoke the corrected string-aware comment scanner exactly once. Raw preserves historical tokens; normalized applies the same historical identifier/number rules. Literal contents remain tokenized, as specified by the corrected scanner's existing scope.

The pattern adapter uses the exact historical 38 regular expressions plus five summary formulas: call_before_write, solc_version, pre_08, log1p(nonblank scanned lines), and log1p(function word count). It implements these directly on the scanned text and never calls a historical helper that strips comments again. Otherwise a comment-like sequence within a quoted string could reintroduce the known bug. Physical line boundaries are preserved; comment-only lines do not enter the denominator.

Pattern counts deliberately retain literal contents, keeping their declared lexical-heuristic meaning. Thus inert quoted code can contribute matches. Only the pragma summary masks quoted strings, so a quoted `pragma solidity` does not become an active compiler version. Missing/unrecognized active pragma keeps the historical numeric fallback (version=0, pre_08=0), with a separate coverage flag. This is not a Solidity parser; function segmentation in call_before_write is lexical and may span constructs beyond a real function body. No count establishes a vulnerability. Corrected comments, retained physical lines and active pragma handling are explicit preprocessing changes, so full numerical equivalence to the old buggy adapter is not claimed.

## Errors and coverage

Every input has a coverage row. Invalid UTF-8, unfinished strings/comments and empty token streams are explicit preprocessing failures. Valid matrix rows carry their sample IDs and original matrix-row mapping; failed rows have no synthetic feature vector. A post-vocabulary all-zero external row is retained with `representation_status='zero_vocabulary_vector'` and `feature_ready=false`; a future scorer must not invent a safe prediction for it. An empty/entirely failed external batch returns a 0×V matrix and its complete error coverage. Models are never invoked by these operations.

`coverage_20261026_v1` records a single real-input preprocessing pass under its saved plan and copied code. A subsequent independent review requested stricter pattern-training and training-identity API guards. These are recorded in `api_amendment_after_coverage.json`; the original coverage outputs and snapshot are preserved, while `adapter_plan.json` and `current_source_snapshot` describe the final API. AST hashes verify that every pure representation function is unchanged, so no second real-source pass was needed. That command does not fit even a training vocabulary. Consequently it can establish source/token/pattern availability, but cannot establish final TF-IDF nonzero-vector coverage, compiler/tool success, model scores, accuracy or runtime. Those require the later authorized execution stage.

## Tests and recovery

Run the synthetic adapter and input-guard tests:

```bash
.venv/bin/python -m pytest -q papers/security_evaluation/revision1/external_protocol/adapters_v1
```

Tests cover clean historical formulas, comment-order failures, quoted comment markers, active versus quoted pragmas, declared literal-sensitive counts, line denominators, raw/normalized tokens, errors and identity mapping, training-only vocabulary/IDF/scaler, state immutability, refit/overlap refusal, empty/OOV handling and manifest hash mismatches. There are no real human labels or external model fits in the fixtures. The final suite contains 24 tests, including the independent-review guard amendments.

`private_restoration_receipt.json` records exact restoration of the original 180-case coordinator key, 180 renamed source copies (170 distinct files), training proxy key and separate 17 identity-evidence cases. The original public packet is unchanged. All deterministic regenerated public artifacts, including packet_manifest.json, match original hashes; a newly generated plan timestamp exists only in an ignored reproduction directory. Review working forms remain blank, and the 17 identity cases remain quarantined. Private materials must remain ignored and must not be published.

The original B freeze/score gates remain unchanged. Independent engineering review, weighted-performance tooling, verified toolchain artifacts and their final prospective integration still need assessment at the protocol level. Named independent specialists, human protocol/class-mapping sign-off, a prospective freeze, sealed reviews and adjudication are not completed by these adapters.
