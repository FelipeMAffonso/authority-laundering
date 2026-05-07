#!/usr/bin/env bash
# Build the theory paper to PDF.
# Run from the theory/ directory: bash build.sh
set -e
cd "$(dirname "$0")"

PANDOC_PDFLATEX="${PDFLATEX:-pdflatex}"

$PANDOC_PDFLATEX -interaction=nonstopmode -halt-on-error bayesian_source_reliability.tex
bibtex bayesian_source_reliability || true
$PANDOC_PDFLATEX -interaction=nonstopmode -halt-on-error bayesian_source_reliability.tex
$PANDOC_PDFLATEX -interaction=nonstopmode -halt-on-error bayesian_source_reliability.tex

echo "Built bayesian_source_reliability.pdf"
