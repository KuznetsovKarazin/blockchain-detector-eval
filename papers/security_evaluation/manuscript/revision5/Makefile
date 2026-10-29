DOCS = main supplement
REVIEW_DOCS = main_review supplement_review titlepage

all:
	@for doc in $(DOCS); do latexmk -pdf -interaction=nonstopmode -halt-on-error $$doc.tex || exit $$?; done

review:
	@for doc in $(REVIEW_DOCS); do latexmk -pdf -interaction=nonstopmode -halt-on-error $$doc.tex || exit $$?; done

clean:
	latexmk -c $(addsuffix .tex,$(DOCS))
