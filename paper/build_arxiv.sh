#!/bin/bash
# Build arXiv submission package from markdown sources
# Usage: bash paper/build_arxiv.sh  (from projects/authority-laundering/)
#
# Pipeline:  main.md + supplementary.md  ->  Python preprocessor  ->  Pandoc  ->  merged.tex
#            + figures/*.png (600 DPI)  ->  arxiv_submission.zip
#
# arXiv processes this with pdflatex. Figures are PNG to avoid
# font-embedding issues between XeLaTeX-generated PDFs and pdflatex.

set -e

# --- Paths (override on a different machine by editing these three lines) ---
# Pandoc path: uses /c/Program Files/Pandoc/pandoc.exe on this machine.
# Alternative user-local install path: /c/Users/natal/AppData/Local/Pandoc/pandoc
PANDOC="/c/Users/felip/AppData/Local/Pandoc/pandoc.exe"
PYTHON="C:/Users/felip/AppData/Local/Programs/Python/Python313/python.exe"
PDFLATEX="/c/Users/felip/AppData/Local/Programs/MiKTeX/miktex/bin/x64/pdflatex.exe"

PAPER_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$PAPER_DIR")"
TEMPLATE_DIR="$(dirname "$(dirname "$PROJECT_DIR")")/templates"
CSL="$TEMPLATE_DIR/csl/nature.csl"
ARXIV_DIR="$PAPER_DIR/arxiv"
ARXIV_TEX="$PAPER_DIR/arxiv-template.tex"

cd "$PAPER_DIR"

echo "=== Building arXiv submission package ==="

# -- Step 1: Preprocess markdown ---------------------------------
echo "  [1/5] Preprocessing markdown..."
"$PYTHON" - << 'PYEOF'
import re, os

paper_dir = os.environ.get("PAPER_DIR", ".")
arxiv_dir = os.path.join(paper_dir, "arxiv")
os.makedirs(arxiv_dir, exist_ok=True)

# Read source files
with open(os.path.join(paper_dir, "main.md"), encoding="utf-8") as f:
    main_md = f.read()

supp_path = os.path.join(paper_dir, "supplementary.md")
if os.path.exists(supp_path):
    with open(supp_path, encoding="utf-8") as f:
        supp_md = f.read()
else:
    supp_md = ""

# Strip YAML frontmatter from supplementary
supp_md = re.sub(r'^---\n.*?\n---\n', '', supp_md, count=1, flags=re.DOTALL)

# Wrap bare \newpage lines in raw LaTeX blocks (Pandoc needs this)
supp_md = re.sub(
    r'^\\newpage\s*$',
    '\n```{=latex}\n\\\\newpage\n```\n',
    supp_md,
    flags=re.MULTILINE
)

# Build supplementary title block
supp_title = r"""
```{=latex}
\newpage

\begin{center}
{\LARGE\bfseries Supplementary Information for:\\[0.5em]
Authority laundering in large language models\par}

\vspace{0.8em}

{\large Felipe M. Affonso\par}

\vspace{0.3em}

{\small\itshape Spears School of Business, Oklahoma State University, Stillwater, USA\par}
\end{center}

\vspace{1em}
```

"""

# Combine
if supp_md.strip():
    combined = main_md + "\n\n" + supp_title + supp_md
else:
    combined = main_md

# Write
out_path = os.path.join(arxiv_dir, "_combined.md")
with open(out_path, "w", encoding="utf-8") as f:
    f.write(combined)

print(f"  Combined markdown: {len(combined):,} chars")
PYEOF

export PAPER_DIR
echo "  [OK]"

# -- Step 2: Pandoc -> LaTeX -------------------------------------
echo "  [2/5] Pandoc -> LaTeX..."
"$PANDOC" "$ARXIV_DIR/_combined.md" \
  --citeproc \
  --csl="$CSL" \
  --bibliography=references.bib \
  --resource-path="$PAPER_DIR:$PROJECT_DIR" \
  --template="$ARXIV_TEX" \
  --wrap=none \
  --syntax-highlighting=none \
  -o "$ARXIV_DIR/merged.tex" 2>&1

echo "  [OK] merged.tex"

# -- Step 3: Copy figures (PNG only - avoids font issues) -------
echo "  [3/5] Copying PNG figures..."
rm -rf "$ARXIV_DIR/figures" 2>/dev/null
mkdir -p "$ARXIV_DIR/figures"

# Authority-laundering has 7 main figures (fig1-fig7) plus the supplementary heatmap.
FIGS=(
  fig1
  fig2
  fig3_headline
  fig4_per_model
  fig5_per_domain
  fig6_generational
  fig7_grounding
  fig_s_heatmap
)

MISSING=0
for fig in "${FIGS[@]}"; do
  if [ -f "figures/${fig}.png" ]; then
    cp "figures/${fig}.png" "$ARXIV_DIR/figures/"
  else
    echo "  [WARN] Missing: figures/${fig}.png"
    MISSING=$((MISSING + 1))
  fi
done
COPIED=$(ls "$ARXIV_DIR/figures/" | wc -l)
echo "  [OK] $COPIED figures copied ($MISSING missing)"

# -- Step 4: Post-process .tex -----------------------------------
echo "  [4/5] Post-processing .tex..."
"$PYTHON" - << 'PYEOF'
import os, re

arxiv_dir = os.path.join(os.environ.get("PAPER_DIR", "."), "arxiv")
tex_path = os.path.join(arxiv_dir, "merged.tex")

with open(tex_path, encoding="utf-8") as f:
    tex = f.read()

# Ensure all figure references use .png (Pandoc may emit without extension)
# The markdown references .png, so Pandoc should preserve that, but verify
for ext in ['.pdf']:
    tex = re.sub(r'(figures/[a-z0-9_]+)' + re.escape(ext), r'\1.png', tex)

# Remove any stray escaped markdown headings that slipped through
# (e.g., \#\# should not appear in the body)
tex = re.sub(r'\\#\\# ', r'\\subsection*{', tex)
# ^ This is a safety net; shouldn't be needed after proper preprocessing

# Clean up temp artifacts
combined_md = os.path.join(arxiv_dir, "_combined.md")
if os.path.exists(combined_md):
    os.remove(combined_md)

with open(tex_path, "w", encoding="utf-8") as f:
    f.write(tex)

# Verify figure count
import glob
fig_refs = re.findall(r'\\includegraphics.*?\{(figures/[^}]+)\}', tex)
fig_files = set(os.path.basename(f) for f in glob.glob(os.path.join(arxiv_dir, "figures", "*.png")))
print(f"  Figure references in .tex: {len(fig_refs)}")
print(f"  Figure files in figures/:  {len(fig_files)}")

# Check each reference has a matching file
for ref in fig_refs:
    basename = os.path.basename(ref)
    if basename not in fig_files:
        print(f"  [WARN] Referenced but missing: {ref}")

# Check key sections exist
sections = re.findall(r'\\(?:section|subsection|subsubsection)\{([^}]+)\}', tex)
print(f"  Sections in .tex: {len(sections)}")

# Check for escaped ## (should be 0)
escaped = len(re.findall(r'\\#\\#', tex))
if escaped:
    print(f"  [WARN] {escaped} escaped ## found - headings may not render")
else:
    print(f"  [OK] No escaped markdown headings")

PYEOF

echo "  [OK]"

# -- Step 5: Compile + zip ---------------------------------------
echo "  [5/5] Compiling and packaging..."

# Create 00README.XXX
cat > "$ARXIV_DIR/00README.XXX" << 'ARXIVEOF'
nohypertex
ARXIVEOF

# Test compile (2 passes for cross-refs)
cd "$ARXIV_DIR"
"$PDFLATEX" -interaction=nonstopmode merged.tex > /dev/null 2>&1
"$PDFLATEX" -interaction=nonstopmode merged.tex > /dev/null 2>&1

# Check for real errors (not just warnings)
ERRORS=$(grep -c "^!" merged.log 2>/dev/null || echo 0)
PAGES=$(grep -oP 'Output written on merged.pdf \(\K[0-9]+' merged.log 2>/dev/null || echo "?")
echo "  Compiled: $PAGES pages, $ERRORS errors"

if [ "$ERRORS" -gt 0 ]; then
  echo "  LaTeX errors found:"
  grep "^!" merged.log | head -5
fi

# Create zip
cd "$ARXIV_DIR"
rm -f "$PAPER_DIR/arxiv_submission.zip" 2>/dev/null
if command -v zip &>/dev/null; then
  zip -r "$PAPER_DIR/arxiv_submission.zip" merged.tex figures/ 00README.XXX
else
  powershell -Command "Compress-Archive -Path 'merged.tex','figures','00README.XXX' -DestinationPath '../arxiv_submission.zip' -Force"
fi
cd "$PAPER_DIR"

# Clean build artifacts
rm -f "$ARXIV_DIR"/merged.{aux,log,out,toc} 2>/dev/null

echo ""
echo "=== Done ==="
echo "  Upload:  $PAPER_DIR/arxiv_submission.zip"
echo "  Preview: $ARXIV_DIR/merged.pdf ($PAGES pages)"
echo "  Figures: $COPIED PNG files at 600 DPI"
