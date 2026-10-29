"""Build R5 BibTeX from verified R4 records and retained Crossref metadata.

Writes only revision3/journal_literature. Reference 1 remains author-supplied
forthcoming-book metadata; no publication year, ISBN, or DOI is fabricated.
"""
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REV = HERE.parent.parent
old = json.loads((REV/'revision2/literature/ORIGINAL_REFERENCES_NORMALIZED.json').read_text())['records']
additional = json.loads((HERE/'ADDITIONAL_REGISTRATION_METADATA.json').read_text())['records']
core = json.loads((REV/'revision2/literature/VERIFIED_REFERENCES_20261028.json').read_text())['core_records']
renumber = json.loads((REV/'revision2/manuscript_notes/REFERENCE_RENUMBERING.json').read_text())
key_by_number = {
1:'kuznetsovForthcomingBlockchain',2:'kaufman2012leakage',3:'kapoor2023leakage',
4:'lopes2017dejavu',5:'allamanis2019duplication',6:'petti2022independent',
7:'teufel2023graphpart',8:'atasguvenilir2023dti',9:'wu2018moleculenet',
10:'roberts2017cv',11:'joeres2025datasail',12:'herbold2018cpdp',
13:'deng2023multimodal',14:'zhang2024heterogeneous',15:'chakraborty2022vulnerability',
16:'croft2023dataquality',17:'ding2025primevul',18:'risse2024limits',
19:'risse2025wrongexam',20:'kondo2020cloning',21:'ferreira2020smartbugs',
22:'durieux2020tools',23:'ghaleb2020solidifi',24:'zheng2024dappscan',
25:'salzano2026tools',26:'khalid2026transfer',
}
records = []
for r0 in old:
    r = dict(r0)
    r['r4_number'] = renumber[str(r['r3_number'])]
    r['key'] = key_by_number[r['r4_number']]
    r['verification_status'] = 'independently_verified_publication_metadata'
    records.append(r)

newmap = {key_by_number[n]:n for n in range(6,15)}
coremap = {r['id']:r for r in core}
for a in additional:
    if a['key'] not in newmap:
        continue
    assert a['status'] == 'verified_registration_metadata'
    c = a['metadata']; prior = coremap[a['key']]
    r = {
        'key':a['key'],'r4_number':newmap[a['key']],
        'authors':[{k:v.replace('\\xa0',' ').replace('\u00a0',' ') for k,v in x.items() if k in ['given','family']} for x in c['author']],
        'title':prior['title'],'venue':prior['journal'],'year':prior['year'],
        'volume':c.get('volume'),'issue':c.get('issue'),
        'pages':c.get('page'),'article_number':c.get('article-number'),
        'doi':prior['doi'],'url':'https://doi.org/'+prior['doi'],
        'type':'journal-article','publisher':c.get('publisher'),
        'metadata_sources':[{'url':a['metadata_source'],'kind':'Crossref registration metadata'},
                            {'url':prior['primary_url'],'kind':'Primary publication; verified in R4 literature audit','web_refs':prior['refs']}],
        'verification_status':'independently_verified_publication_metadata',
    }
    if r['key'] in ['petti2022independent','deng2023multimodal','zhang2024heterogeneous']:
        r['article_number']=prior['pages_or_article'];r['pages']=None
    records.append(r)

records.append({
    'r4_number':1,'key':key_by_number[1],
    'authors':[{'given':'Oleksandr','family':'Kuznetsov'}],
    'title':'Custom AI Solutions for Blockchain Systems: Detection and Prevention of Anomalies',
    'publisher':'CRC Press / Taylor & Francis','year':'forthcoming','type':'book',
    'verification_status':'author_supplied_forthcoming_status_not_independently_verified',
    'metadata_sources':[{'path':'papers/security_evaluation/manuscript/DRAFT_REVISION4.md','kind':'Author manuscript, reference 1'}],
    'notes':['Exact-title publisher searches returned no independently verifiable catalogue record. No ISBN, DOI or numeric year is supplied. Confirm accepted/in-press status and access to Chapter 13 before journal upload; otherwise cite as an unpublished book manuscript.'],
})
records.sort(key=lambda r:r['r4_number'])
assert [r['r4_number'] for r in records] == list(range(1,27))

# Retain the name printed in the original paper, not an aggregator's expanded identity.
records[25]['metadata_sources'].extend([
    {'url':'https://drops.dagstuhl.de/storage/00lipics/lipics-vol394-esem2026/LIPIcs.ESEM.2026.45/LIPIcs.ESEM.2026.45.pdf','kind':'Original publisher PDF, first page','web_ref':'turn117view0'},
    {'url':'https://chbrown13.github.io/publications.html','kind':'Author publication list','web_ref':'turn116search2'},
])
records[25]['notes'].append('Original published authorship is Chris Brown; retain Brown, Chris. An OpenAlex expanded display name is not used to rewrite publication authorship.')

y = next(x for x in additional if x['key']=='yilmaz2008incomplete')['metadata']
supplement = [{
    'supplement_number':1,'key':'yilmaz2008incomplete','type':'journal-article',
    'authors':[{k:v for k,v in x.items() if k in ['given','family']} for x in y['author']],
    'title':y['title'][0],'venue':y['container-title'][0],'volume':y['volume'],'issue':y['issue'],
    'pages':y['page'],'year':2008,'doi':'10.1007/s10115-007-0101-7',
    'url':'https://doi.org/10.1007/s10115-007-0101-7',
    'verification_status':'independently_verified_publication_metadata',
    'metadata_sources':[{'url':'https://api.crossref.org/works/10.1007/s10115-007-0101-7','kind':'Crossref registration metadata'}],
},{
    'supplement_number':2,'key':'hfcn2023methodological','type':'report',
    'corporate_author':'Household Finance and Consumption Network',
    'title':'Household Finance and Consumption Survey: Methodological Report for the 2021 Wave',
    'institution':'European Central Bank','series':'Statistics Paper Series','number':'45','year':2023,
    'doi':'10.2866/970554','isbn':'978-92-899-6107-3',
    'url':'https://www.ecb.europa.eu/pub/pdf/scpsps/ecb.sps45~4bbcfb02eb.en.pdf',
    'verification_status':'independently_verified_publication_metadata',
    'metadata_sources':[{'url':'https://www.ecb.europa.eu/pub/pdf/scpsps/ecb.sps45~4bbcfb02eb.en.pdf','kind':'Official PDF, title/copyright pages','web_ref':'turn119view1'}],
    'notes':['Section 7.2 is the cited passage; include that locator in the citation, not in the report title.'],
}]

accents = {'á':r"{\'a}",'é':r"{\'e}",'í':r"{\'i}",'ó':r"{\'o}",'ú':r"{\'u}",
           'Á':r"{\'A}",'É':r"{\'E}",'ö':r'{\"o}','ü':r'{\"u}','ñ':r'{\~n}',
           'ã':r'{\~a}','ğ':r'{\u{g}}','Ş':r'{\c{S}}','ş':r'{\c{s}}',
           'ø':r'{\o}','å':r'{\aa}','à':r'{\`a}','‐':'-','–':'--','—':'---','’':"'",'−':'-'}
def tex(s):
    s = str(s).replace('\\xa0',' ').replace('\u00a0',' ')
    return ''.join(accents.get(ch, {'&':r'\&','%':r'\%','#':r'\#','_':r'\_'}.get(ch,ch)) for ch in s)

def bib(r):
    typ={'journal-article':'article','proceedings-article':'inproceedings','book':'book','report':'techreport'}[r['type']]
    f={}
    if r.get('corporate_author'):
        f['author'] = '{'+r['corporate_author']+'}'
    else:
        f['author'] = ' and '.join(a['family']+', '+a['given'] for a in r['authors'])
    f['title']='{'+r['title']+'}'
    if typ=='article':f['journal']=r['venue']
    elif typ=='inproceedings':f['booktitle']=r['venue']
    if r.get('volume'):f['volume']=r['volume']
    if r.get('issue'):f['number']=r['issue']
    if r.get('pages'):f['pages']=r['pages'].replace('-','--')
    if r.get('article_number'):
        f['eid']=r['article_number']
        if not r.get('pages'):f['pages']=r['article_number']
        elif r['key']=='lopes2017dejavu':f['pages']='84:1--84:28'
        elif r['key']=='kaufman2012leakage':f['pages']='15:1--15:21'
        elif r['key']=='risse2025wrongexam':f['note']='Article ISSTA018'
    f['year']=r['year']
    if r.get('publisher') and typ in ['book','inproceedings']:f['publisher']=r['publisher']
    if r.get('series') and typ=='inproceedings':f['series']=r['series']
    if typ=='techreport':
        f['institution']=r['institution'];f['type']=r['series'];f['number']=r['number']
    if r.get('isbn'):f['isbn']=r['isbn']
    if r.get('doi'):f['doi']=r['doi']
    if r.get('url'):f['url']=r['url']
    if typ=='book':f['note']='Forthcoming; Chapter 13'
    lines=['@'+typ+'{'+r['key']+',']
    for k,v in f.items():
        # DOI/URL syntax is passed literally; all current URLs are BibTeX-safe.
        value=str(v) if k in ['doi','url'] else tex(v)
        lines.append('  '+k+' = {'+value+'},')
    lines.append('}')
    return '\n'.join(lines)

header='% R5 normalized bibliography. Publication metadata verified except the author-supplied forthcoming book.\n% Evidence and source records: REFERENCES_VERIFICATION.json. No invented DOI.\n\n'
(HERE/'references.bib').write_text(header+'\n\n'.join(bib(r) for r in records)+'\n')
(HERE/'supplement_references.bib').write_text('% Supplement references; original publication metadata verified.\n\n'+'\n\n'.join(bib(r) for r in supplement)+'\n')
(HERE/'CITATION_KEY_MAP.json').write_text(json.dumps({'r4_main':key_by_number,'r4_supplement':{r['supplement_number']:r['key'] for r in supplement}},ensure_ascii=False,indent=2)+'\n')
(HERE/'REFERENCES_VERIFICATION.json').write_text(json.dumps({'scope':'Metadata audit; scientific claim review is in revision2/literature/VERIFIED_REFERENCES_20261028.json.','main_records':records,'supplement_records':supplement,'counts':{'main':26,'main_independently_verified':25,'main_author_supplied':1,'supplement_independently_verified':2}},ensure_ascii=False,indent=2)+'\n')
for filename,expected in [('references.bib',26),('supplement_references.bib',2)]:
    s=(HERE/filename).read_text();assert len(re.findall(r'^@',s,re.M))==expected
    assert s.count('{')==s.count('}')
    print(filename,expected,'entries',len(s.encode()),'bytes')
