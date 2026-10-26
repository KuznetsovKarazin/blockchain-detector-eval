"""Synthetic fixtures only; no actual external fit, prediction or judgment."""
import hashlib
import json
from pathlib import Path
import sys
import unittest

import numpy as np
from sklearn.exceptions import NotFittedError

sys.path.insert(0, str(Path(__file__).parent))
import adapters as a
from bal.features.contract_features import pattern_features


def rec(i, source, role='train'):
    return a.SourceRecord(i, role, source)


class AdapterTests(unittest.TestCase):
    def test_exact_43_feature_names_and_definitions(self):
        d = a.feature_definitions()
        self.assertEqual(len(d['feature_names']), 43)
        self.assertEqual(len(d['regex_features']), 38)
        self.assertEqual([r['name'] for r in d['regex_features']] + [r['name'] for r in d['summary_features']], d['feature_names'])

    def test_clean_fixture_preserves_historical_feature_formulas(self):
        source = 'pragma solidity ^0.5.0;\ncontract C {\n function f() public {\n msg.sender.send(1);\n balance[msg.sender] -= 1;\n }\n}'
        actual = a.Pattern43().transform([rec('clean', source)]).matrix[0]
        expected = [pattern_features(source)[name] for name in a.PATTERN_NAMES]
        np.testing.assert_allclose(actual, expected, rtol=1e-6)

    def test_block_marker_inside_line_comment_does_not_hide_active_code(self):
        source = '// /* inert opening marker\ncontract C { function f() public { to.call.value(1)(""); balances[msg.sender] -= 1; } }'
        row = a.Pattern43().transform([rec('comment-order', source)]).matrix[0]
        self.assertGreater(row[a.PATTERN_NAMES.index('call_value')], 0)
        self.assertGreater(row[a.PATTERN_NAMES.index('call_before_write')], 0)

    def test_literal_comment_markers_never_trigger_second_comment_strip(self):
        source = 'contract C { string u = "https://host/*literal*/"; function f() public { to.send(1); } }'
        row = a.Pattern43().transform([rec('url', source)]).matrix[0]
        self.assertGreater(row[a.PATTERN_NAMES.index('send')], 0)
        self.assertGreater(row[a.PATTERN_NAMES.index('n_functions')], 0)

    def test_pragma_excludes_quoted_and_commented_declarations(self):
        source = '// pragma solidity ^0.4.0;\nstring fake = "pragma solidity ^0.5.0;";\npragma solidity ^0.8.7;\ncontract C {}'
        row = a.Pattern43().transform([rec('pragma', source)]).matrix[0]
        self.assertAlmostEqual(float(row[a.PATTERN_NAMES.index('solc_version')]), .08, places=6)
        self.assertEqual(row[a.PATTERN_NAMES.index('pre_08')], 0)

    def test_literal_sensitive_pattern_policy_is_explicit_and_stable(self):
        source = 'contract C { string inert = "function to.send(1)"; }'
        result = a.Pattern43().transform([rec('literal', source)])
        self.assertGreater(result.matrix[0, a.PATTERN_NAMES.index('send')], 0)
        self.assertTrue(result.coverage[0]['pattern_literal_contents_retained'])
        self.assertTrue(result.coverage[0]['pragma_version_missing'])

    def test_corrected_comment_scan_preserves_physical_line_denominator(self):
        source = 'contract C { /* first\ncomment */ function f() public {} }'
        result = a.Pattern43().transform([rec('lines', source)])
        self.assertEqual(result.coverage[0]['nonblank_scanned_lines'], 2)
        self.assertAlmostEqual(result.matrix[0, a.PATTERN_NAMES.index('loc')], np.log1p(2), places=6)

    def test_raw_and_normalized_keep_corrected_historical_token_rules(self):
        source = 'contract Unique { uint arbitraryName = 123; string s = "//kept"; }'
        raw = a.prepare([rec('x', source)], 'raw').texts[0]
        norm = a.prepare([rec('x', source)], 'normalized').texts[0]
        self.assertIn('arbitraryName', raw)
        self.assertNotIn('arbitraryName', norm)
        self.assertIn('NUM', norm)
        self.assertIn('kept', raw)
        self.assertIn('contract', norm)

    def test_error_coverage_preserves_every_identity_and_matrix_mapping(self):
        rows = [rec('valid', 'contract C {}', 'external'), rec('decode', b'\xff', 'external'),
                rec('scan', '/* unfinished', 'external'), rec('empty', '// only comment', 'external')]
        result = a.Pattern43().transform(rows)
        self.assertEqual(result.row_ids, ('valid',))
        self.assertEqual(result.matrix.shape, (1, 43))
        self.assertEqual([r['preprocessing_status'] for r in result.coverage], ['ready', 'decode_error', 'scanner_error', 'empty_token_stream'])
        self.assertEqual([r['matrix_row'] for r in result.coverage], [0, None, None, None])
        self.assertTrue(all(not r['model_scoring_performed'] for r in result.coverage))

    def test_vocabulary_idf_and_scaler_fit_only_train_and_transform_is_immutable(self):
        for representation in ('raw', 'normalized'):
            fit = a.TrainOnlyTfidf(representation)
            train = [rec('tr1', 'contract common {}'), rec('tr2', 'contract common { uint a; }'), rec('tr3', 'contract common { uint b; }')]
            result = fit.fit_transform_training(train)
            before = fit.state_sha256()
            variance = fit._scaler.var_.copy(); idf = fit._vectorizer.idf_.copy()
            out = fit.transform([rec('ex', 'contract HELDOUT_ONLY { address ONLY_EXTERNAL; }', 'external')])
            self.assertEqual(before, fit.state_sha256())
            np.testing.assert_array_equal(variance, fit._scaler.var_)
            np.testing.assert_array_equal(idf, fit._vectorizer.idf_)
            self.assertNotIn('HELDOUT_ONLY', fit._vectorizer.vocabulary_)
            self.assertEqual(fit.training_state_metadata()['fit_rows'], 3)
            self.assertEqual(result.matrix.shape[1], out.matrix.shape[1])

    def test_external_or_mixed_fit_rejected(self):
        for rows in ([rec('ex', 'common', 'external')], [rec('tr', 'common'), rec('ex', 'common', 'external')]):
            with self.assertRaises(ValueError):a.TrainOnlyTfidf('raw').fit_transform_training(rows)

    def test_refit_and_external_identity_overlap_rejected(self):
        fit = a.TrainOnlyTfidf('raw'); train = [rec('tr1', 'common'), rec('tr2', 'common')]
        fit.fit_transform_training(train)
        with self.assertRaises(RuntimeError):fit.fit_transform_training(train)
        with self.assertRaises(ValueError):fit.transform([rec('tr1', 'common', 'external')])

    def test_transform_before_fit_rejected(self):
        with self.assertRaises(NotFittedError):a.TrainOnlyTfidf('raw').transform([rec('ex', 'common', 'external')])

    def test_invalid_training_input_does_not_silently_drop_or_fit(self):
        fit = a.TrainOnlyTfidf('raw')
        with self.assertRaises(a.TrainingInputError) as caught:
            fit.fit_transform_training([rec('ok', 'common'), rec('bad', '"unfinished')])
        self.assertEqual(caught.exception.coverage[1]['preprocessing_status'], 'scanner_error')
        with self.assertRaises(NotFittedError):fit.state_sha256()

    def test_unavailable_training_vocabulary_fails_closed(self):
        with self.assertRaises(a.TrainingInputError):
            a.TrainOnlyTfidf('raw').fit_transform_training([rec('a', 'distinctA'), rec('b', 'distinctB')])

    def test_zero_vocabulary_external_vector_is_flagged_not_safe_score(self):
        fit = a.TrainOnlyTfidf('raw'); fit.fit_transform_training([rec('a', 'common'), rec('b', 'common')])
        result = fit.transform([rec('ex', 'completely_unseen', 'external')])
        self.assertEqual(result.matrix.nnz, 0)
        self.assertEqual(result.coverage[0]['representation_status'], 'zero_vocabulary_vector')
        self.assertFalse(result.coverage[0]['feature_ready'])
        self.assertNotIn('score', result.coverage[0])

    def test_empty_transform_and_bad_rows_keep_feature_dimension(self):
        fit = a.TrainOnlyTfidf('raw'); fit.fit_transform_training([rec('a', 'common'), rec('b', 'common')])
        empty = fit.transform([]); bad = fit.transform([rec('bad', b'\xff', 'external')])
        self.assertEqual(empty.matrix.shape, (0, 1)); self.assertEqual(bad.matrix.shape, (0, 1))
        self.assertEqual(len(bad.coverage), 1)

    def test_duplicate_identity_or_unknown_role_rejected(self):
        with self.assertRaises(ValueError):a.prepare([rec('same', 'a'), rec('same', 'b')], 'raw')
        with self.assertRaises(ValueError):a.prepare([rec('x', 'a', 'unspecified')], 'raw')

    def test_feature_definition_file_matches_code(self):
        path = Path(__file__).parent / 'feature_definitions.json'
        self.assertEqual(json.loads(path.read_text()), a.feature_definitions())



class FactoryAndInputTests(unittest.TestCase):
    def test_four_methods_map_to_declared_unfitted_representations(self):
        self.assertIsInstance(a.adapter_for_method('raw_tfidf_lr'), a.TrainOnlyTfidf)
        self.assertIsInstance(a.adapter_for_method('normalized_tfidf_lr'), a.TrainOnlyTfidf)
        self.assertIsInstance(a.adapter_for_method('pattern_rf'), a.Pattern43)
        self.assertIsInstance(a.adapter_for_method('pattern_lgbm'), a.Pattern43)
        with self.assertRaises(ValueError):a.adapter_for_method('unregistered')

    def test_manifest_hash_mismatch_rejected_before_source_access(self):
        import tempfile
        import check_coverage
        with tempfile.TemporaryDirectory() as folder:
            packet=Path(folder)
            (packet/'protected.csv').write_text('changed')
            (packet/'public_file_hashes.json').write_text(json.dumps({'protected.csv':hashlib.sha256(b'original').hexdigest()}))
            with self.assertRaisesRegex(ValueError,'Frozen packet hash changed'):
                check_coverage.load_verified_records(packet)

    def test_numeric_sample_id_is_not_an_implicit_identity(self):
        with self.assertRaises(ValueError):a.prepare([a.SourceRecord(1,'train','common')], 'raw')


class TrainingProvenanceAmendmentTests(unittest.TestCase):
    def test_pattern_training_guard_never_drops_invalid_source(self):
        adapter=a.Pattern43()
        with self.assertRaises(a.TrainingInputError):
            adapter.fit_transform_training([rec('valid','contract C {}'),rec('invalid','/* unfinished')])
        with self.assertRaises(ValueError):
            adapter.fit_transform_training([rec('external','contract C {}','external')])
        valid=adapter.fit_transform_training([rec('a','contract C {}'),rec('b','contract D {}')])
        self.assertEqual(valid.row_ids,('a','b'))
        self.assertEqual(valid.matrix.shape,(2,43))
        self.assertIsNone(valid.state_sha256)

    def test_changed_or_unknown_training_provenance_is_rejected(self):
        adapter=a.TrainOnlyTfidf('raw')
        adapter.fit_transform_training([rec('a','common'),rec('b','common')])
        with self.assertRaisesRegex(ValueError,'fitted training provenance'):
            adapter.transform([rec('a','common changed')])
        with self.assertRaisesRegex(ValueError,'fitted training provenance'):
            adapter.transform([rec('unknown','common')])
        self.assertEqual(adapter.transform([rec('a','common')]).row_ids,('a',))

if __name__ == '__main__':unittest.main()
