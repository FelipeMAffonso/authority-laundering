#!/usr/bin/env bash
# Build fig1: render fig1.html to PDF + PNG in two variants.
#   fig1_full.pdf / fig1_full.png     — with caption (standalone viewing / OSF release)
#   fig1.pdf      / fig1.png           — without caption (for the paper markdown)
#
# fig1.html is the source of truth; edit it, then run this.
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
  # $1 = URL suffix (e.g., "" or "?nocaption")
  # $2 = output basename (e.g., "fig1_full" or "fig1")
  local suffix="$1"
  local base="$2"
  local tmppdf="${TMPDIR:-/tmp}/${base}_build.pdf"
  rm -f "$tmppdf"
  local url="file:///$(cygpath -m "$HERE")/fig1.html${suffix}"
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
import numpy as np
from PIL import Image
doc = pymupdf.open(r"${here_win}/${base}.pdf")
pix = doc[0].get_pixmap(dpi=300)
raw_path = r"${here_win}/${base}.png"
pix.save(raw_path)
# Tight crop: anything with min-channel < 245 counts as content. Standard
# ImageChops.difference leaves anti-aliased grey borders as "non-white" and
# produces a loose crop; threshold on raw min-value is much tighter.
img = Image.open(raw_path).convert("RGB")
arr = np.asarray(img)
mask = arr.min(axis=2) < 245
rows = np.where(mask.any(axis=1))[0]
cols = np.where(mask.any(axis=0))[0]
if len(rows) and len(cols):
    top, bottom = int(rows[0]), int(rows[-1]) + 1
    left, right = int(cols[0]), int(cols[-1]) + 1
    img.crop((left, top, right, bottom)).save(raw_path)
    img = Image.open(raw_path)
print(f"  wrote ${base}.pdf  +  ${base}.png  ({img.width} x {img.height}, tight-crop)")
PY
}

render_variant ""            "fig1_full"
render_variant "?nocaption"  "fig1"

echo "Done."
