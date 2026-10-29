"""Normalize R3 bibliography metadata from retained registration and primary records.

No manuscript is modified. Run after fetch_reference_metadata.py.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
raw = json.loads((HERE / 'ORIGINAL_REFERENCE_REGISTRATION_METADATA.json').read_text())
records = []
for item in raw['records']:
    if item['status'] != 'verified_registration_metadata':
        continue
    c = item['crossref']
    title = c['title'][0]
    if c.get('subtitle'):
        title += ': ' + c['subtitle'][0]
    date = c.get('published-print') or c.get('published') or c['issued']
    r = {
        'r3_number': item['r3_number'],
        'authors': c['author'],
        'title': title,
        'venue': c['container-title'][0],
        'year': date['date-parts'][0][0],
        'volume': c.get('volume'),
        'issue': c.get('issue'),
        'pages': c.get('page'),
        'article_number': c.get('article-number'),
        'page_count': None,
        'doi': c['DOI'],
        'url': 'https://doi.org/' + c['DOI'],
        'publisher': c.get('publisher'),
        'type': c.get('type'),
        'registered_print_date': c.get('published-print'),
        'registered_online_date': c.get('published-online'),
        'metadata_sources': [{'url': item['metadata_source'], 'kind': 'Crossref DOI registration metadata'}],
        'verification_scope': 'Bibliographic metadata only; this normalization does not assert full-text scientific-claim review.',
        'notes': [],
    }
    if r['article_number'] and r['pages'] == r['article_number']:
        r['pages'] = None
    records.append(r)

by_n = {r['r3_number']: r for r in records}
by_n[2].update(article_number='15', page_count=21)
by_n[2]['metadata_sources'].append({'url':'https://dl.acm.org/doi/10.1145/2382577.2382579','kind':'Publisher metadata (search retrieval; direct open returned 403)','web_ref':'turn106search0'})
by_n[4].update(article_number='84', page_count=28)
by_n[4]['metadata_sources'].append({'url':'https://janvitek.org/pubs/oopsla17b.pdf','kind':'Author-hosted published article, first-page ACM reference format','web_ref':'turn110view0'})
by_n[5]['notes'].append('The proceedings title identifies Onward! 2019; Crossref event metadata identifies the co-located SPLASH 2019 umbrella event.')
by_n[6]['notes'].append('Use final issue year 2022; the 2021 embedded in the DOI is not the final issue year.')
by_n[7]['notes'].append('Registered author name is M. Mehdi Kholoosi, retaining the first initial omitted in R3.')
by_n[10].update(article_number='ISSTA018', page_count=23)
by_n[10]['metadata_sources'].append({'url':'https://github.com/niklasrisse/TopScoreWrongExam/blob/main/README.md','kind':'Author repository citation block','web_ref':'turn109view1'})
by_n[10]['notes'].append('The author citation gives Article ISSTA018, 23 pages; Crossref gives continuous pages 388–410. Either locator convention is legitimate; the formatted list uses the article convention consistently with other ACM article-number publications.')
by_n[11]['notes'].append('Registered author name is Zhen Ming Jiang; an informal nickname is unnecessary in the reference.')
by_n[12]['notes'].append('Use ASE 2020 proceedings/event year 2020, not the later online metadata date 2021-01-27.')
by_n[16]['notes'].append('143 is an article number, not a page. Final issue is 31(5), September 2026; first online was 2026-05-16.')

records.append({
    'r3_number':9,
    'authors':[{'given':'Niklas','family':'Risse'},{'given':'Marcel','family':'Böhme'}],
    'title':'Uncovering the Limits of Machine Learning for Automatic Vulnerability Detection',
    'venue':'33rd USENIX Security Symposium (USENIX Security 24)',
    'year':2024,'volume':None,'issue':None,'pages':'4247-4264','article_number':None,'page_count':None,
    'doi':None,'url':'https://www.usenix.org/conference/usenixsecurity24/presentation/risse',
    'publisher':'USENIX Association','isbn':'978-1-939133-44-1','type':'proceedings-article',
    'metadata_sources':[{'url':'https://www.usenix.org/conference/usenixsecurity24/presentation/risse','kind':'Official publisher BibTeX','web_ref':'turn110view1'}],
    'verification_scope':'Bibliographic metadata; scientific claims were separately reviewed in the earlier literature audit.',
    'notes':['The publisher provides no DOI in its official citation; no DOI has been invented.'],
})
records.append({
    'r3_number':17,
    'authors':[{'given':'Shawal','family':'Khalid'},{'given':'Joaquin','family':'Tuckett'},{'given':'Chris','family':'Brown'}],
    'title':'Do Smart Contract Auditing Results Transfer Across Datasets? A Two-Benchmark Empirical Study of Static and LLM-Based Security Tools',
    'venue':'20th International Symposium on Empirical Software Engineering and Measurement (ESEM 2026)',
    'series':'Leibniz International Proceedings in Informatics (LIPIcs)',
    'year':2026,'volume':'394','issue':None,'pages':'45:1-45:21','article_number':None,'page_count':21,
    'doi':'10.4230/LIPIcs.ESEM.2026.45','url':'https://doi.org/10.4230/LIPIcs.ESEM.2026.45',
    'publisher':'Schloss Dagstuhl – Leibniz-Zentrum für Informatik','isbn':'978-3-95977-450-5','type':'proceedings-article',
    'publication_date':'2026-10-05',
    'metadata_sources':[{'url':'https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.ESEM.2026.45','kind':'Official publisher Cite As and BibTeX','web_ref':'turn110view3'}],
    'verification_scope':'Bibliographic metadata only; this normalization does not assert full-text scientific-claim review.',
    'notes':['Crossref retrieval returned HTTP 404; publisher metadata independently verifies all fields.'],
})
records.sort(key=lambda r:r['r3_number'])
assert [r['r3_number'] for r in records] == list(range(2,18))

def formatted(r):
    authors = '; '.join(a['given'] + ' ' + a['family'] for a in r['authors'])
    title_end = '' if r['title'].endswith(('?', '!', '.')) else '.'
    s = f"[{r['r3_number']}] {authors}. {r['title']}{title_end} *{r['venue']}*"
    if r.get('series'):
        s += f". {r['series']}, vol. {r['volume']}"
    elif r['volume']:
        s += f", {r['volume']}"
        if r['issue']:
            s += f"({r['issue']})"
    s += f", {r['year']}"
    if r['article_number']:
        s += f", Article {r['article_number']}"
        if r['page_count']:
            s += f", {r['page_count']} pp."
        else:
            s += '.'
    elif r['pages']:
        s += f", pp. {r['pages'].replace('-', '–')}."
    else:
        s += '.'
    if r['type'] == 'proceedings-article':
        s += f" {r['publisher']}."
    if r['doi']:
        s += f" DOI: [{r['doi']}]({r['url']})."
    else:
        s += f" [Official proceedings page]({r['url']})."
    return s

for r in records:
    r['formatted_reference'] = formatted(r)

out = {
    'schema':'article1_original_references_normalized_v1',
    'date':'2026-10-28',
    'scope':'Original R3 references 2–17; old numbering is retained as a mapping, not as the final manuscript order.',
    'source':raw['source'],'source_sha256':raw['source_sha256'],
    'registration_evidence':'ORIGINAL_REFERENCE_REGISTRATION_METADATA.json',
    'verification_summary':{'Crossref_records':14,'publisher_or_author_supplements':5,'unresolved_required_fields':0},
    'records':records,
}
(HERE/'ORIGINAL_REFERENCES_NORMALIZED.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')

md = '''# Original R3 references 2–17: normalized metadata

Prepared 2026-10-28. These labels retain the **R3 numbering for mapping**; the manuscript owner should renumber by first citation after integration. This pass checks publication metadata, not every scientific claim made in the cited papers. Crossref registration records and retrieval provenance are retained in `ORIGINAL_REFERENCE_REGISTRATION_METADATA.json`; field-specific publisher/author supplements are recorded in `ORIGINAL_REFERENCES_NORMALIZED.json`.

## Ready-formatted list

'''
md += '\n\n'.join(r['formatted_reference'] for r in records)
md += '''

## Material corrections and conventions

| R3 reference | Correction or interpretation |
|---|---|
| [2] Kaufman et al. | TKDD 6(4), Article 15, 21 pages; the subtitle is part of the title. |
| [4] Lopes et al. | PACMPL 1(OOPSLA), Article 84, 28 pages, verified from the published PDF on an author's website. |
| [6] Chakraborty et al. | IEEE TSE 48(9), 3280–3296, **2022**; do not infer the publication year from the DOI's 2021 component. |
| [7] Croft et al. | Preserve the registered author name **M. Mehdi Kholoosi**. |
| [9] Risse and Böhme | Replace “Official proceedings” as bibliographic content with USENIX Security 24, 4247–4264, USENIX Association. The official citation supplies no DOI. |
| [10] Risse et al. | PACMSE 2(ISSTA), Article ISSTA018, 23 pages. Crossref's continuous pages 388–410 are an alternative locator; the list uses the author-supplied article identifier consistently. |
| [12] Ferreira et al. | ASE **2020**, 1349–1352. The online metadata date in January 2021 does not change the conference year. |
| [16] Salzano et al. | EMSE **31(5), Article 143 (2026)**. First-online May and final-issue September are distinct metadata dates. |
| [17] Khalid et al. | ESEM 2026, LIPIcs **394**, 45:1–45:21. Crossref returned 404; the official Dagstuhl Cite As and BibTeX supply complete metadata. |

All 16 entries have a verified venue and either page range or article identifier. No book or report has been assigned invented journal fields; those original references lie outside this 2–17 mapping. No references were added to meet a numerical quota.
'''
(HERE/'ORIGINAL_REFERENCES_FORMATTED.md').write_text(md)
print(f'Wrote {len(records)} normalized references and formatted list.')
