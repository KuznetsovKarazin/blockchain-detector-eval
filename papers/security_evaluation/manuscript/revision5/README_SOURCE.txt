LaTeX sources for How Dependency-Graph Construction Changes Training Eligibility in Smart Contract Vulnerability Benchmarks

main.tex: author-named manuscript.
supplement.tex: complete supplementary material.
The separate submission package also supplies main_review.tex and supplement_review.tex: versions with direct author/funding/repository identifiers removed; the historical self-reference is blinded.
Its titlepage.tex contains separate author, correspondence, funding and replication details.
references.bib is the core numbered bibliography; the optional review copies use references_review.bib.
figure1.pdf through figure6.pdf and figureS1.pdf through figureS3.pdf: vector figures.
Highlights.docx/Highlights.txt and cover_letter.txt are additional submission-package files.

Build from this flat directory using TeX Live with pdfLaTeX and latexmk:
  make
The optional review/title-page files can be compiled with make review.
For one document:
  latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex

Select the appropriate manuscript version and supply the title page separately according to the journal's current instructions. The official elsarticle class and numeric bibliography style are included unchanged; their license notices are retained, with elsarticle.dtx and elsarticle.ins providing the class source. The manuscript uses standard TeX Live packages including amsmath, graphicx, longtable, booktabs, geometry, microtype, xurl, pdflscape, hyperref and orcidlink.

The main.md and supplement.md files preserve scientific authoring text. Changes to the TeX do not automatically update them. The repository provides the conversion script and analysis/plotting sources; they are distinct from compilation of this submission package.

Replication release:
https://github.com/KuznetsovKarazin/blockchain-detector-eval/releases/tag/article1-r5-2026-10-29
Full reproducibility archive DOI: https://doi.org/10.5281/zenodo.23750089
