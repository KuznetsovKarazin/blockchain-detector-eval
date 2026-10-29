#!/usr/bin/env python3
"""Build the flat Elsevier source directory from the authored R5 Markdown.

Scientific edits belong in manuscript/revision5/{main,supplement}.md. This
converter handles only presentation, citations, and portable asset names.
"""
from __future__ import annotations
import json
import re
import subprocess
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
OUT = BASE / 'manuscript' / 'revision5'
MAP = OUT / 'citation_map.json'

def pandoc(s: str) -> str:
    return subprocess.run(['pandoc', '-f', 'markdown+tex_math_single_backslash+raw_tex-fancy_lists', '-t', 'latex', '--wrap=none', '--shift-heading-level-by=-1'], input=s, text=True, capture_output=True, check=True).stdout.strip()

def citations(s: str, mapping: dict[str, str]) -> str:
    protected=[]
    def protect(m):
        protected.append(m.group(0))
        return f'CITATIONPROTECTEDTOKEN{len(protected)-1}END'
    s=re.sub(r'\\\[[\s\S]*?\\\]|\\\([\s\S]*?\\\)|`[^`]*`',protect,s)
    def sub(m):
        nums=re.split(r'\s*,\s*', m.group(1))
        if all(n in mapping for n in nums):
            return r'\cite{' + ','.join(mapping[n] for n in nums) + '}'
        raise ValueError(f'Unmapped citation {m.group(0)}')
    s=re.sub(r'(?<!\!)\[(\d+(?:\s*,\s*\d+)*)\](?!\()', sub, s)
    for i,p in enumerate(protected):
        s=s.replace(f'CITATIONPROTECTEDTOKEN{i}END',p)
    return s

ASSETS = {
    'fig03_scope_ablation.png': 'figure1.pdf',
    'fig01_thresholds.png': 'figure2.pdf',
    'fig02_population.png': 'figure3.pdf',
    'fig04_representation_controls.png': 'figure4.pdf',
    'fig05_sampling_variance.png': 'figure5.pdf',
    'fig06_external_flow.png': 'figureS1.pdf',
}

def convert_figures(s: str) -> str:
    pattern=r'!\[([^\]]*)\]\(([^\n]+)\)\s*\n\s*\*Figure\s+(S?\d+)\.\s*(.*?)\*'
    def sub(m):
        asset=ASSETS.get(Path(m.group(2)).name,Path(m.group(2)).name)
        if not (OUT/asset).exists(): raise FileNotFoundError(asset)
        cap=pandoc(m.group(4))
        if asset=='figureS3.pdf':
            return '\n\\clearpage\n\\begin{landscape}\n\\begin{figure}[p]\n\\centering\n'+rf'\includegraphics[width=235mm,height=135mm,keepaspectratio]{{{asset}}}'+'\n'+rf'\caption{{{cap}}}\label{{fig:{m.group(3)}}}'+'\n\\end{figure}\n\\end{landscape}\n\\clearpage\n'
        return '\n\\begin{figure}[htbp]\n\\centering\n'+rf'\includegraphics[width=\linewidth,height=0.75\textheight,keepaspectratio]{{{asset}}}'+'\n'+rf'\caption{{{cap}}}\label{{fig:{m.group(3)}}}'+'\n\\end{figure}\n'
    return re.sub(pattern,sub,s,flags=re.S)

def convert_tables(s: str, supp: bool) -> str:
    lines=s.splitlines(); out=[]; i=0; table_num=0
    while i<len(lines):
        caption=''
        if lines[i].startswith('**Table '):
            capline=lines[i]
            match=re.match(r'\*\*Table\s+S?\d+\.\s*(.*?)\*\*(.*)',capline)
            if not match: raise ValueError(capline)
            caption=(match.group(1)+match.group(2)).strip()
            i+=1
            while i<len(lines) and not lines[i].strip(): i+=1
            if i>=len(lines) or not lines[i].startswith('|'): raise ValueError('Table caption without table')
        if lines[i].startswith('|'):
            rows=[]
            while i<len(lines) and lines[i].startswith('|'):
                rows.append([x.strip() for x in lines[i].strip().strip('|').split('|')]);i+=1
            if len(rows)<2 or not all(re.fullmatch(r':?-+:?',x.replace(' ','')) for x in rows[1]): raise ValueError('Invalid markdown table')
            headers=rows[0]; data=rows[2:]; n=len(headers); table_num+=1
            if any(len(row)!=n for row in data): raise ValueError('Ragged table')
            ratios={2:[.29,.71],3:[.34,.33,.33],4:[.23,.23,.27,.27],5:[.21,.1975,.1975,.1975,.1975],6:[.19,.15,.19,.15,.16,.16]}.get(n,[1/n]*n)
            if not supp and table_num==1: ratios=[.21,.15,.27,.37]
            if not supp and table_num==3: ratios=[.20,.18,.19,.18,.25]
            if supp and 'Reproduction scenario' in headers: ratios=[.27,.32,.41]
            if supp and headers[0]=='Test seed': ratios=[.11,.14,.18,.21,.18,.18]
            specs=''.join(r'>{\raggedright\arraybackslash}p{\dimexpr '+f'{r:.5f}'+r'\linewidth-2\tabcolsep\relax}' for r in ratios)
            def row(r,bold=False):
                cells=[pandoc(c).replace('\n',' ').replace('Library/interface','Library/\\allowbreak interface') for c in r]
                if bold: cells=[r'\textbf{'+c+'}' for c in cells]
                return ' & '.join(cells)+r' \\'
            block=['\n\\begingroup','\\small','\\setlength{\\tabcolsep}{4pt}','\\setlength{\\LTcapwidth}{\\linewidth}','\\renewcommand{\\arraystretch}{1.14}',rf'\begin{{longtable}}{{{specs}}}']
            if caption: block.append(r'\caption{'+pandoc(caption)+r'}\label{tab:'+('S' if supp else '')+str(table_num)+r'}\\')
            block.extend([r'\toprule',row(headers,True),r'\midrule',r'\endfirsthead',r'\toprule',row(headers,True),r'\midrule',r'\endhead',r'\midrule',rf'\multicolumn{{{n}}}{{r}}{{\footnotesize Continued on next page}} \\',r'\endfoot',r'\bottomrule',r'\endlastfoot'])
            block.extend(row(r) for r in data)
            block.extend([r'\end{longtable}',r'\endgroup',''])
            out.extend(block)
        else:
            out.append(lines[i]);i+=1
    return '\n'.join(out)

PREAMBLE=r'''\documentclass[preprint,12pt]{elsarticle}
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\DeclareUnicodeCharacter{2212}{\ensuremath{-}}
\usepackage{lmodern}
\usepackage[a4paper,margin=25mm]{geometry}
\usepackage{amsmath,amssymb}
\usepackage{booktabs,longtable,array,tabularx}
\usepackage{graphicx}
\usepackage{pdflscape}
\usepackage{xcolor}
\usepackage{microtype}
\usepackage{xurl}
\usepackage[section]{placeins}
\usepackage[hidelinks]{hyperref}
\usepackage{orcidlink}
\urlstyle{same}
\hypersetup{pdfauthor={Oleksandr Kuznetsov},pdftitle={How Dependency-Graph Construction Changes Training Eligibility in Smart Contract Vulnerability Benchmarks}}
\providecommand{\tightlist}{\setlength{\itemsep}{0pt}\setlength{\parskip}{0pt}}
\setlength{\emergencystretch}{2em}
\setcounter{secnumdepth}{3}
\journal{Blockchain: Research and Applications}
'''

def build(kind: str, mapping: dict[str,str]) -> None:
    s=(OUT/f'{kind}.md').read_text()
    s=s.split('\n## References\n')[0]
    supp=kind=='supplement'
    if supp:
        title=s.splitlines()[0][2:]
        s='\n'.join(s.splitlines()[1:])
        s=re.sub(r'^(#{2,4})\s+S\d+(?:\.\d+)*\.?(?:\s+)',r'\1 ',s,flags=re.M)
        front=r'\begin{document}'+'\n'+r'\begin{center}\Large\bfseries '+pandoc(title)+r'\end{center}'+'\n'+r'\renewcommand{\thesection}{S\arabic{section}}\renewcommand{\thetable}{S\arabic{table}}\renewcommand{\thefigure}{S\arabic{figure}}'+'\n'
    else:
        title=s.splitlines()[0][2:]
        abstract=s.split('## Abstract\n\n',1)[1].split('\n**Keywords:**',1)[0].strip()
        keywords=s.split('**Keywords:** ',1)[1].split('\n',1)[0]
        s='## 1. Introduction'+s.split('## 1. Introduction',1)[1]
        s=re.sub(r'^(#{2,4})\s+\d+(?:\.\d+)*\.?\s+',r'\1 ',s,flags=re.M)
        front=r'''\begin{document}
\begin{frontmatter}
\title{'''+pandoc(title)+r'''}
\author[ecampus,karazin]{Oleksandr Kuznetsov\corref{cor1}\orcidlink{0000-0003-2331-6326}}
\ead{oleksandr.kuznetsov@uniecampus.it}
\cortext[cor1]{Corresponding author.}
\affiliation[ecampus]{organization={Department of Theoretical and Applied Sciences, eCampus University},country={Italy}}
\affiliation[karazin]{organization={Department of Intelligent Software Systems and Technologies, School of Computer Science and Artificial Intelligence, V.N. Karazin Kharkiv National University},country={Ukraine}}
\begin{abstract}
'''+pandoc(abstract)+r'''
\end{abstract}
\begin{keyword}
'''+r' \sep '.join(pandoc(k.strip()) for k in keywords.split(';'))+r'''
\end{keyword}
\end{frontmatter}
'''
    s=citations(s,mapping)
    s=convert_figures(s)
    s=convert_tables(s,supp)
    body=pandoc(s)
    body=re.sub(r'\\hypertarget\{[^}]+\}\{%\n(\\(?:sub)*section\*?\{[^\n]+\})\}',r'\1',body)
    body=re.sub(r'\\texttt\{([0-9a-f]{40,64})\}',r'\\nolinkurl{\1}',body)
    body=re.sub(r'\\texttt\{((?:[A-Za-z0-9./:\-]|\\_){25,})\}',lambda m:r'\nolinkurl{'+m.group(1).replace(r'\_','_')+'}',body)
    # These statements follow the numbered scientific sections.
    for title in ['Data and code availability','Declaration of generative AI and AI-assisted technologies in the manuscript preparation process','Funding','Declaration of competing interest','CRediT authorship contribution statement']:
        body=body.replace(r'\section{'+title+'}',r'\section*{'+title+'}')
    output=PREAMBLE+front+body+'\n\\FloatBarrier\n\\bibliographystyle{elsarticle-num}\n\\bibliography{references}\n\\end{document}\n'
    expected_figures=s.count(r'\begin{figure}')
    assert output.count(r'\begin{figure}')==expected_figures==output.count(r'\end{figure}')
    assert r'\textbackslash begin' not in output
    assert r'\textbackslash caption' not in output
    (OUT/f'{kind}.tex').write_text(output)
    print(f'{kind}: {len(s.split())} body words, {output.count(chr(92)+"includegraphics")} figures')

def review_versions() -> None:
    """Separate review copies without changing the named archival sources."""
    main=(OUT/'main.tex').read_text()
    main=re.sub(r'\\author\[ecampus,karazin\].*?(?=\\begin\{abstract\})','',main,flags=re.S)
    main=main.replace('pdfauthor={Oleksandr Kuznetsov}','pdfauthor={}')
    main=main.replace(r'\emph{Custom AI Solutions for Blockchain Systems: Detection and Prevention of Anomalies}', 'the previously reported baseline study')
    main=main.replace('Chapter 13 of the previously reported baseline study','the previously reported baseline study')
    pat=r'(\\section\*\{Data and code availability\}.*?\n)(.*?)(?=\\section\*\{|\\FloatBarrier)'
    main=re.sub(pat,lambda m:m.group(1)+'\nThe public replication artifact is identified on the separate title page supplied to the editor. Direct identifying links are omitted from this review copy. Supplement S5 describes archive lineage, required inputs and the scope of the executed verification.\n\n',main,flags=re.S)
    main=re.sub(r'\\section\*\{Funding\}.*?(?=\\section\*\{|\\FloatBarrier)','',main,flags=re.S)
    main=main.replace('kuznetsovForthcomingBlockchain','historicalBaseline').replace(r'\bibliography{references}',r'\bibliography{references_review}')
    (OUT/'main_review.tex').write_text(main)
    supp=(OUT/'supplement.tex').read_text().replace('pdfauthor={Oleksandr Kuznetsov}','pdfauthor={}')
    # The substantive lineage/limitations remain; direct public account identifiers do not.
    supp=re.sub(r'(\\section\{Reproducibility and archive lineage\}\\label\{[^}]+\}\n+)(.*?)(?=\n\n)',lambda m:m.group(1)+'The public replication artifact is identified on the separate title page supplied to the editor. The retrieval script verifies the evidence archive and its members before restoring the recorded paths. The following scenarios distinguish inspection, metric recomputation and refitting.',supp,flags=re.S)
    supp=supp.replace(r'\bibliography{references}',r'\bibliography{references_review}')
    (OUT/'supplement_review.tex').write_text(supp)
    bib=(OUT/'references.bib').read_text()
    start=bib.index('@book{kuznetsovForthcomingBlockchain,');end=bib.index('\n\n@',start)
    bib=bib[:start]+'''@misc{historicalBaseline,
  author = {{Author details withheld for review}},
  title = {{Previously reported historical baseline}},
  note = {Full reference supplied in the non-anonymous manuscript},
}
'''+bib[end:]
    (OUT/'references_review.bib').write_text(bib)
    title='How Dependency-Graph Construction Changes Training Eligibility in Smart Contract Vulnerability Benchmarks'
    page=r'''\documentclass[12pt]{article}
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage[a4paper,margin=25mm]{geometry}
\usepackage{lmodern}
\usepackage{xurl}
\usepackage{microtype}
\setlength{\emergencystretch}{2em}
\usepackage[hidelinks]{hyperref}
\usepackage{orcidlink}
\pagestyle{empty}
\begin{document}
\begin{center}
{\Large\bfseries '''+title+r'''}\par\vspace{15mm}
{\large Oleksandr Kuznetsov\textsuperscript{1,2}\orcidlink{0000-0003-2331-6326}}\par\vspace{6mm}
\textsuperscript{1}Department of Theoretical and Applied Sciences, eCampus University, Italy.\par\vspace{4mm}
\textsuperscript{2}Department of Intelligent Software Systems and Technologies, School of Computer Science and Artificial Intelligence, V.N. Karazin Kharkiv National University, Ukraine.
\end{center}
\vspace{12mm}
\noindent Corresponding author: Oleksandr Kuznetsov\par
\noindent Email: \href{mailto:oleksandr.kuznetsov@uniecampus.it}{oleksandr.kuznetsov@uniecampus.it}\par
\noindent ORCID: \href{https://orcid.org/0000-0003-2331-6326}{0000-0003-2331-6326}\par
\vspace{8mm}
\noindent Journal: \emph{Blockchain: Research and Applications}\par
\noindent Article type: Research article
\par\vspace{8mm}
\noindent Replication materials: \\
\url{https://github.com/KuznetsovKarazin/blockchain-detector-eval/releases/tag/article1-r5-2026-10-29}
\par\noindent Archival DOI: \href{https://doi.org/10.5281/zenodo.23750089}{10.5281/zenodo.23750089}
\par\vspace{8mm}
\noindent\textbf{Funding}\par
'''+pandoc((OUT/'funding_statement.txt').read_text())+r'''
\end{document}
'''
    (OUT/'titlepage.tex').write_text(page)

if __name__=='__main__':
    m=json.loads(MAP.read_text())
    build('main',m['main']);build('supplement',m['supplement']);review_versions()
