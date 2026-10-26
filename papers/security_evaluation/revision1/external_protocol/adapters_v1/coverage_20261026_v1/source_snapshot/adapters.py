"""Versioned feature adapters only: no classifier, external scoring or labels.

Historical token/pattern definitions with one corrected comment scan. Pattern
counts still see literal contents by declaration; only pragma extraction masks
strings. These are source heuristics, not AST or semantic vulnerability facts.
"""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Sequence

import numpy as np
from scipy import sparse
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import StandardScaler
from sklearn.exceptions import NotFittedError

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'papers/security_evaluation/normalization_audit'))
from bal.features.contract_features import KEEP, TOKEN_RE, PATTERNS, PATTERN_NAMES
from solidity_scanner import scan_comments, normalize_scanned_text, SolidityScanError

REPRESENTATIONS = ('raw', 'normalized', 'pattern43')
TFIDF_PARAMETERS = dict(token_pattern=r'\S+', ngram_range=(1, 3), min_df=2,
                        max_features=50000, sublinear_tf=True, lowercase=False)
SCALER_PARAMETERS = dict(with_mean=False)

@dataclass(frozen=True)
class SourceRecord:
    sample_id: str
    role: str
    source: str | bytes

@dataclass
class PreparedBatch:
    representation: str
    records: tuple[SourceRecord, ...]
    row_ids: tuple[str, ...]
    texts: tuple[str, ...]
    patterns: np.ndarray | None
    coverage: list[dict]

@dataclass
class TransformedBatch:
    matrix: object
    row_ids: tuple[str, ...]
    coverage: list[dict]
    state_sha256: str | None

class TrainingInputError(ValueError):
    def __init__(self, message, coverage):
        self.coverage = coverage
        super().__init__(message)


def mask_literal_contents(scanned: str) -> str:
    """Mask quotes only after a successful scan; preserve offsets/newlines."""
    chars = list(scanned)
    i = 0
    while i < len(scanned):
        if scanned[i] not in '\"\'':
            i += 1
            continue
        quote, start = scanned[i], i
        i += 1
        while i < len(scanned):
            if scanned[i] == '\\':
                i += 2
            elif scanned[i] == quote:
                i += 1
                break
            else:
                i += 1
        for j in range(start, min(i, len(scanned))):
            if chars[j] not in '\r\n':
                chars[j] = ' '
    return ''.join(chars)


def pattern_from_scanned(scanned: str) -> tuple[np.ndarray, dict]:
    """Exactly 38 historical regexes + 5 declared summary features.

    Never call a helper that strips comments a second time. Regex patterns and
    call-before-write remain literal-sensitive and non-AST heuristics. Version
    is taken from the first *active* pragma (literal contents excluded).
    """
    loc = max(1, sum(bool(line.strip()) for line in scanned.splitlines()))
    result = {}
    for name, regex in PATTERNS.items():
        count = len(re.findall(regex, scanned, re.M if name == 'unchecked_call_stmt' else 0))
        result[name] = 100.0 * count / loc
    calls = 0
    for function_part in re.split(r'\bfunction\b', scanned)[1:]:
        call = re.search(r'\.call\.value\s*\(|\.call\s*\{[^}]*value|\.send\s*\(|\.transfer\s*\(', function_part)
        if call and re.search(r'\w+\s*\[[^\]]+\]\s*(=|-=|\+=)', function_part[call.end():]):
            calls += 1
    result['call_before_write'] = 100.0 * calls / loc
    pragma = re.search(r'\bpragma\s+solidity\s*[\^>=<~ ]*\s*(\d+)\.(\d+)', mask_literal_contents(scanned))
    version = int(pragma.group(1)) + int(pragma.group(2)) / 100.0 if pragma else None
    result['solc_version'] = float(version) if version is not None else 0.0
    result['pre_08'] = float(version is not None and version < .08)
    result['loc'] = float(np.log1p(loc))
    result['n_functions'] = float(np.log1p(len(re.findall(r'\bfunction\b', scanned))))
    values = np.asarray([result[name] for name in PATTERN_NAMES], dtype=np.float32)
    if len(values) != 43 or not np.isfinite(values).all():
        raise ValueError('Pattern definition/finite-value invariant failed')
    return values, {'nonblank_scanned_lines': loc, 'pragma_version_missing': version is None,
                    'pattern_literal_contents_retained': True}


def prepare(records: Sequence[SourceRecord], representation: str) -> PreparedBatch:
    if representation not in REPRESENTATIONS:
        raise ValueError('Unknown representation')
    records = tuple(records)
    if any(not isinstance(r, SourceRecord) or not isinstance(r.sample_id, str) or not r.sample_id or r.role not in ('train', 'external') for r in records):
        raise ValueError('Unique named records with explicit train/external role are required')
    if len({r.sample_id for r in records}) != len(records):
        raise ValueError('Duplicate sample identity')
    texts, patterns, row_ids, coverage = [], [], [], []
    for record in records:
        if not isinstance(record.source, (bytes, str)):
            raise TypeError('Source must be bytes or text')
        raw = record.source if isinstance(record.source, bytes) else record.source.encode('utf-8')
        status = dict(sample_id=record.sample_id, role=record.role,
                      source_sha256=hashlib.sha256(raw).hexdigest(),
                      preprocessing_status='ready', matrix_row=None,
                      model_scoring_performed=False)
        try:
            source = raw.decode('utf-8', errors='strict')
            scanned = scan_comments(source)
            tokens = TOKEN_RE.findall(scanned.text)
            status.update(raw_token_count=len(tokens), line_comments=scanned.line_comments,
                          block_comments=scanned.block_comments, string_literals=scanned.string_literals)
            if not tokens:
                status['preprocessing_status'] = 'empty_token_stream'
            else:
                status['matrix_row'] = len(row_ids)
                row_ids.append(record.sample_id)
                if representation == 'pattern43':
                    vector, extra = pattern_from_scanned(scanned.text)
                    patterns.append(vector)
                    status.update(extra)
                else:
                    texts.append(' '.join(tokens) if representation == 'raw' else normalize_scanned_text(scanned.text))
        except UnicodeDecodeError:
            status['preprocessing_status'] = 'decode_error'
        except SolidityScanError as exc:
            status.update(preprocessing_status='scanner_error', scanner_error_code=exc.code,
                          scanner_error_line=exc.line, scanner_error_column=exc.column)
        coverage.append(status)
    matrix = np.vstack(patterns) if patterns else np.empty((0, 43), dtype=np.float32)
    return PreparedBatch(representation, records, tuple(row_ids), tuple(texts),
                         matrix if representation == 'pattern43' else None, coverage)


def feature_definitions() -> dict:
    regexes = [dict(index=i, name=name, regex=regex,
                    flags='MULTILINE' if name == 'unchecked_call_stmt' else '',
                    value='100 * regex match count / max(1, nonblank scanned lines)')
               for i, (name, regex) in enumerate(PATTERNS.items())]
    summaries = {
        'call_before_write': '100 * count of lexical function segments containing value-call then mapping assignment / nonblank scanned lines; not AST or flow analysis',
        'solc_version': 'first active pragma major + minor/100, strings masked; missing/unrecognized => 0',
        'pre_08': '1 iff recognized active pragma version < .08, else 0',
        'loc': 'log1p(max(1, nonblank lines after corrected comment scanning))',
        'n_functions': 'log1p(word-boundary function count after corrected scanning; literals retained)',
    }
    return dict(schema='external_B_feature_definitions_v1', feature_names=list(PATTERN_NAMES),
                regex_features=regexes,
                summary_features=[dict(index=38+i, name=name, value=definition) for i, (name, definition) in enumerate(summaries.items())],
                token_regex=TOKEN_RE.pattern, normalization_keep=sorted(KEEP),
                comment_policy='single corrected string-aware scan; no legacy second strip',
                lexical_literal_policy='contents retained with historical token regex',
                pattern_literal_policy='contents retained for counts; masked only for active pragma version',
                pattern_line_policy='comment blanking preserves physical newlines; comment-only lines excluded',
                limitations=['no AST or type analysis', 'quoted inert code may affect pattern counts',
                             'call-before-write function segmentation is lexical, not actual control flow',
                             'compiler acceptance and semantic vulnerability are not established'])


class TrainOnlyTfidf:
    """One fit on explicitly training-role records; every later use transforms.

    This interface prevents accidental role/refit mistakes, not a caller falsely
    relabelling an external record as training. The input-manifest verifier must
    provide the fixed training identities. Invalid training inputs fail closed.
    """
    def __init__(self, representation: str):
        if representation not in ('raw', 'normalized'):
            raise ValueError('TFIDF supports raw or normalized only')
        self.representation = representation
        self._vectorizer = None
        self._scaler = None
        self._training_ids = None
        self._training_source_sha256 = None

    def fit_transform_training(self, records: Sequence[SourceRecord]) -> TransformedBatch:
        if self._vectorizer is not None:
            raise RuntimeError('Adapter already fitted; refitting is prohibited')
        records = tuple(records)
        if not records or any(not isinstance(record, SourceRecord) or record.role != 'train' for record in records):
            raise ValueError('Fit accepts a nonempty explicitly training-only batch')
        prepared = prepare(records, self.representation)
        if any(row['preprocessing_status'] != 'ready' for row in prepared.coverage):
            raise TrainingInputError('Invalid training sources; no silent training-row exclusion', prepared.coverage)
        vectorizer = TfidfVectorizer(**TFIDF_PARAMETERS)
        try:
            values = vectorizer.fit_transform(prepared.texts)
        except ValueError as exc:
            raise TrainingInputError('Training vocabulary unavailable: ' + str(exc), prepared.coverage) from exc
        if (values.getnnz(axis=1) == 0).any():
            raise TrainingInputError('Training rows have no retained vocabulary features', prepared.coverage)
        scaler = StandardScaler(**SCALER_PARAMETERS)
        values = scaler.fit_transform(values)
        self._vectorizer, self._scaler = vectorizer, scaler
        self._training_ids = prepared.row_ids
        self._training_source_sha256 = tuple(r['source_sha256'] for r in prepared.coverage)
        return self._result(values, prepared)

    def transform(self, records: Sequence[SourceRecord]) -> TransformedBatch:
        if self._vectorizer is None:
            raise NotFittedError('Training-only fit is required first')
        records = tuple(records)
        if any(not isinstance(r, SourceRecord) for r in records):
            raise ValueError('Explicit SourceRecord inputs required')
        if any(r.role == 'external' and r.sample_id in self._training_ids for r in records):
            raise ValueError('External identity overlaps training identity')
        prepared = prepare(records, self.representation)
        before = self.state_sha256()
        if prepared.texts:
            values = self._scaler.transform(self._vectorizer.transform(prepared.texts))
        else:
            values = sparse.csr_matrix((0, len(self._vectorizer.vocabulary_)), dtype=np.float64)
        if before != self.state_sha256():
            raise RuntimeError('Transform unexpectedly changed fitted state')
        return self._result(values, prepared)

    def _result(self, matrix, prepared):
        nnz = np.asarray(matrix.getnnz(axis=1)).ravel()
        coverage = [dict(row) for row in prepared.coverage]
        for row in coverage:
            i = row['matrix_row']
            row['representation_status'] = (row['preprocessing_status'] if i is None else
                                            'ready' if nnz[i] else 'zero_vocabulary_vector')
            row['feature_ready'] = i is not None and bool(nnz[i])
        return TransformedBatch(matrix, prepared.row_ids, coverage, self.state_sha256())

    def state_sha256(self):
        if self._vectorizer is None:
            raise NotFittedError('No training-fitted state')
        header = dict(representation=self.representation, tfidf=TFIDF_PARAMETERS,
                      scaler=SCALER_PARAMETERS, vocabulary=sorted((word, int(index)) for word, index in self._vectorizer.vocabulary_.items()),
                      training_ids=self._training_ids, training_source_sha256=self._training_source_sha256)
        h = hashlib.sha256(json.dumps(header, sort_keys=True, separators=(',', ':')).encode())
        for values in [self._vectorizer.idf_, self._scaler.mean_, self._scaler.var_, self._scaler.scale_, np.asarray(self._scaler.n_samples_seen_)]:
            array = np.asarray(values)
            h.update(str(array.dtype).encode()); h.update(str(array.shape).encode()); h.update(array.tobytes())
        return h.hexdigest()

    def training_state_metadata(self):
        digest = self.state_sha256()
        return dict(state_sha256=digest, representation=self.representation,
                    training_ids=list(self._training_ids), training_source_sha256=list(self._training_source_sha256),
                    vocabulary_size=len(self._vectorizer.vocabulary_), fit_rows=int(self._scaler.n_samples_seen_),
                    fitted_on='training_manifest_only', external_fit_allowed=False)


class Pattern43:
    """Stateless 43-feature matrix for RF/LGBM; no data-fitted scaler needed."""
    def transform(self, records: Sequence[SourceRecord]) -> TransformedBatch:
        prepared = prepare(records, 'pattern43')
        coverage = [dict(row, representation_status=row['preprocessing_status'],
                         feature_ready=row['preprocessing_status'] == 'ready') for row in prepared.coverage]
        return TransformedBatch(prepared.patterns, prepared.row_ids, coverage, None)


def adapter_for_method(method: str):
    """Construct an unfitted representation adapter, never a classifier."""
    if method == 'raw_tfidf_lr':
        return TrainOnlyTfidf('raw')
    if method == 'normalized_tfidf_lr':
        return TrainOnlyTfidf('normalized')
    if method in ('pattern_rf', 'pattern_lgbm'):
        return Pattern43()
    raise ValueError('Method is outside the four declared B methods')
