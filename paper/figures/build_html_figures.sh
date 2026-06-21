#!/usr/bin/env bash
# Render the HTML figures (fig1, fig2) to PDF + PNG, two variants each:
#   <fig>_full.{pdf,png}  — with caption, for standalone viewing / OSF release
#   <fig>.{pdf,png}        — no caption, for the paper markdown
#
# HTML files at paper/figures/<fig>.html are the source of truth.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

CHROME="/c/Program Files/Google/Chrome/Application/chrome.exe"
PY="C:/Users/felip/AppData/Local/Programs/Python/Python313/python.exe"

if [[ ! -f "$CHROME" ]]; then
  echo "ERROR: Chrome not found at $CHROME" >&2
  exit 1
fi

render_variant () {
  # $1 = source html (e.g. fig1.html)
  # $2 = URL suffix (e.g. "" or "?nocaption")
  # $3 = output basename (e.g. fig1_full or fig1)
  local src="$1"
  local suffix="$2"
  local base="$3"
  local tmppdf="${TMPDIR:-/tmp}/${base}_build.pdf"
  rm -f "$tmppdf"
  local url="file:///$(cygpath -m "$HERE")/${src}${suffix}"
  "$CHROME" --headless=new --disable-gpu --no-sandbox --hide-scrollbars \
            --no-pdf-header-footer \
            --print-to-pdf="$tmppdf" "$url" >/dev/null 2>&1
  cp "$tmppdf" "$HERE/${base}.pdf"
  local here_win
  here_win="$(cygpath -m "$HERE")"
  "$PY" -X utf8 - <<PY
import sys
sys.path.insert(0, 'C:/Users/felip/AppData/Local/Programs/Python/Python313/Lib/site-packages')
import pymupdf
doc = pymupdf.open(r"${here_win}/${base}.pdf")
pix = doc[0].get_pixmap(dpi=300)
pix.save(r"${here_win}/${base}.png")
print(f"  wrote ${base}.pdf  +  ${base}.png  ({pix.width} x {pix.height})")
PY
}

for fig in fig1 fig2; do
  if [[ ! -f "$HERE/${fig}.html" ]]; then
    echo "SKIP: ${fig}.html missing"
    continue
  fi
  echo "Building ${fig}..."
  render_variant "${fig}.html" ""            "${fig}_full"
  render_variant "${fig}.html" "?nocaption"  "${fig}"
done

echo "Done."
