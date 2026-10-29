"""Read-only DOI registration metadata audit, without downloading article bodies."""
from __future__ import annotations
import concurrent.futures
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
SOURCE = ROOT / 'papers/security_evaluation/manuscript/DRAFT_REVISION3.md'


def fetch(item):
    number, doi = item
    url = 'https://api.crossref.org/works/' + quote(doi, safe='/')
    result = {'r3_number': number, 'doi': doi, 'metadata_source': url,
              'retrieved_utc': datetime.now(timezone.utc).isoformat(),
              'scope': 'DOI registration metadata only; no claim of full-text review.'}
    try:
        req = Request(url, headers={'User-Agent': 'Article1BibliographicAudit/1.0'})
        with urlopen(req, timeout=35) as response:
            message = json.load(response)['message']
        wanted = ['DOI', 'title', 'subtitle', 'container-title', 'short-container-title',
                  'publisher', 'volume', 'issue', 'page', 'article-number', 'type',
                  'published', 'published-print', 'published-online', 'issued', 'event',
                  'ISBN', 'ISSN', 'URL', 'link']
        result['crossref'] = {key: message[key] for key in wanted if key in message}
        result['crossref']['author'] = [
            {key: a[key] for key in ['given', 'family', 'name', 'suffix'] if key in a}
            for a in message.get('author', [])]
        result['status'] = 'verified_registration_metadata'
    except Exception as error:
        result['status'] = 'unresolved'
        result['error'] = type(error).__name__ + ': ' + str(error)
    return result


if __name__ == '__main__':
    text = SOURCE.read_text()
    entries = []
    for number, paragraph in re.findall(r'^\[(\d+)\] (.+)$', text, re.M):
        number = int(number)
        if 2 <= number <= 17:
            match = re.search(r'https://doi.org/([^\s)]+)', paragraph)
            if match:
                entries.append((number, match.group(1)))
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(fetch, entries))
    payload = {'schema': 'article1_original_reference_registration_audit_v1',
               'date': '2026-10-28',
               'source': str(SOURCE.relative_to(ROOT)),
               'source_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
               'records': results}
    target = HERE / 'ORIGINAL_REFERENCE_REGISTRATION_METADATA.json'
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n')
    for record in results:
        metadata = record.get('crossref', {})
        print(json.dumps({key: value for key, value in {
            'r3': record['r3_number'], 'status': record['status'], 'doi': record['doi'],
            'title': metadata.get('title'), 'volume': metadata.get('volume'),
            'issue': metadata.get('issue'), 'page': metadata.get('page'),
            'article': metadata.get('article-number'), 'published': metadata.get('published'),
            'error': record.get('error')}.items() if value is not None}, ensure_ascii=False))
