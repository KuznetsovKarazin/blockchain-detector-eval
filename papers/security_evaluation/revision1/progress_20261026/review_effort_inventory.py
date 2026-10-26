"""Count review packet bytes/physical lines without reading keys or judgments."""
from pathlib import Path
import hashlib
import json
import statistics

ROOT = Path(__file__).resolve().parents[4]
SOURCE = ROOT / 'data/derived/revision1_external_review_probability_20261025_v1/blinded_sources'
OUT = Path(__file__).with_name('REVIEW_EFFORT_INVENTORY.json')


def summarize(values):
    values = sorted(values)
    return {'minimum': values[0], 'median': statistics.median(values),
            'maximum': values[-1], 'sum': sum(values),
            'at_least_1000_physical_lines': sum(v >= 1000 for v in values),
            'at_least_5000_physical_lines': sum(v >= 5000 for v in values)}


def main():
    paths = sorted(SOURCE.glob('P*.sol'))
    if len(paths) != 180:
        raise ValueError('Expected unchanged 180-case probability packet')
    rows = []
    for path in paths:
        data = path.read_bytes()
        rows.append({'hash': hashlib.sha256(data).hexdigest(), 'bytes': len(data),
                     'lines': len(data.splitlines())})
    unique = {row['hash']: row for row in rows}
    if len(unique) != 170:
        raise ValueError('Expected 170 distinct source byte streams')
    output = {'schema': 'probability_review_effort_inventory_v1',
              'case_source_copies': len(rows), 'unique_source_byte_streams': len(unique),
              'physical_lines_case_weighted': summarize([r['lines'] for r in rows]),
              'physical_lines_unique_files': summarize([r['lines'] for r in unique.values()]),
              'bytes_case_weighted': sum(r['bytes'] for r in rows),
              'bytes_unique_files': sum(r['bytes'] for r in unique.values()),
              'semantics': 'Physical lines include blanks/comments; not executable LOC or measured review time.',
              'identity_census_included': False, 'sampling_or_population_changed': False,
              'keys_or_judgments_read': False, 'human_judgments_produced': 0,
              'source_body_disclosed': False,
              'note': 'Both specialists still assess every selected file-class case. No cases are replaced for length or convenience.'}
    with OUT.open('x') as stream:
        json.dump(output, stream, indent=2); stream.write('\n')
    print(json.dumps(output))


if __name__ == '__main__':
    main()
