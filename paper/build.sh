#!/bin/bash
# Build authority-laundering paper: markdown -> PDF and DOCX
# Usage: bash paper/build.sh (from projects/authority-laundering/)
#
# Produces:
#   paper/main.docx       - Pandoc + shared reference.docx (Nature-house style)
#   paper/main.pdf        - Pandoc + xelatex + nature-template.tex (Palatino 11pt, line numbers)
#   paper/supplementary.docx
#   paper/supplementary.pdf
#
# If the xelatex build with the Nature template fails (missing fonts, broken
# LaTeX packages), the script falls back to a bare Pandoc+xelatex run with
# basic Palatino geometry so you always get a PDF.

# --- Paths (override on a different machine by editing these two lines) ---
# Pandoc path: uses /c/Program Files/Pandoc/pandoc.exe on this machine.
# Alternative user-local install path: /c/Users/natal/AppData/Local/Pandoc/pandoc
PANDOC="/c/Program Files/Pandoc/pandoc.exe"
XELATEX="/c/Users/natal/AppData/Local/Programs/MiKTeX/miktex/bin/x64/xelatex.exe"

PAPER_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$PAPER_DIR")"
TEMPLATE_DIR="$(dirname "$(dirname "$PROJECT_DIR")")/templates"
CSL="$TEMPLATE_DIR/csl/nature.csl"
REF_DOCX="$TEMPLATE_DIR/pandoc-academic/reference.docx"
NATURE_TEX="$PAPER_DIR/nature-template.tex"

cd "$PAPER_DIR"

echo "Building paper from: $PAPER_DIR"
echo "CSL: $CSL"

# --- Build DOCX ---
echo "  -> Building DOCX..."
"$PANDOC" main.md \
  --citeproc \
  --csl="$CSL" \
  --bibliography=references.bib \
  --reference-doc="$REF_DOCX" \
  --resource-path="$PAPER_DIR:$PROJECT_DIR" \
  --syntax-highlighting=none \
  -o main.docx 2>&1

if [ $? -eq 0 ]; then
  echo "  [OK] main.docx"
else
  echo "  [FAIL] main.docx"
fi

# --- Build PDF (Nature-style via custom template) ---
echo "  -> Building PDF (Nature style)..."
"$PANDOC" main.md \
  --citeproc \
  --csl="$CSL" \
  --bibliography=references.bib \
  --resource-path="$PAPER_DIR:$PROJECT_DIR" \
  --pdf-engine="$XELATEX" \
  --template="$NATURE_TEX" \
  --syntax-highlighting=none \
  -o main.pdf 2>&1

if [ $? -eq 0 ]; then
  echo "  [OK] main.pdf"
else
  echo "  [FAIL] main.pdf -- trying without custom template..."
  "$PANDOC" main.md \
    --citeproc \
    --csl="$CSL" \
    --bibliography=references.bib \
    --resource-path="$PAPER_DIR:$PROJECT_DIR" \
    --pdf-engine="$XELATEX" \
    -H "$PAPER_DIR/fallback_header.tex" \
    -V geometry:margin=1in \
    -V fontsize=11pt \
    -V linestretch=1.15 \
    -V mainfont="Palatino Linotype" \
    --syntax-highlighting=none \
    -o main.pdf 2>&1
  if [ $? -eq 0 ]; then
    echo "  [OK] main.pdf (fallback)"
  else
    echo "  [FAIL] main.pdf"
  fi
fi

# --- Build Supplementary DOCX ---
if [ -f supplementary.md ]; then
  echo "  -> Building Supplementary DOCX..."
  "$PANDOC" supplementary.md \
    --citeproc \
    --csl="$CSL" \
    --bibliography=references.bib \
    --reference-doc="$REF_DOCX" \
    --resource-path="$PAPER_DIR:$PROJECT_DIR" \
    --syntax-highlighting=none \
    -o supplementary.docx 2>&1

  if [ $? -eq 0 ]; then
    echo "  [OK] supplementary.docx"
  else
    echo "  [FAIL] supplementary.docx"
  fi

  # --- Build Supplementary PDF (Nature-style) ---
  echo "  -> Building Supplementary PDF (Nature style)..."
  "$PANDOC" supplementary.md \
    --citeproc \
    --csl="$CSL" \
    --bibliography=references.bib \
    --resource-path="$PAPER_DIR:$PROJECT_DIR" \
    --pdf-engine="$XELATEX" \
    --template="$NATURE_TEX" \
    --syntax-highlighting=none \
    -o supplementary.pdf 2>&1

  if [ $? -eq 0 ]; then
    echo "  [OK] supplementary.pdf"
  else
    echo "  [FAIL] supplementary.pdf -- trying without custom template..."
    "$PANDOC" supplementary.md \
      --citeproc \
      --csl="$CSL" \
      --bibliography=references.bib \
      --resource-path="$PAPER_DIR:$PROJECT_DIR" \
      --pdf-engine="$XELATEX" \
      -H "$PAPER_DIR/fallback_header.tex" \
      -V geometry:margin=1in \
      -V fontsize=11pt \
      -V linestretch=1.15 \
      -V mainfont="Palatino Linotype" \
      --syntax-highlighting=none \
      -o supplementary.pdf 2>&1
    if [ $? -eq 0 ]; then
      echo "  [OK] supplementary.pdf (fallback)"
    else
      echo "  [FAIL] supplementary.pdf"
    fi
  fi
else
  echo "  [SKIP] supplementary.md not present"
fi

echo "Done."
