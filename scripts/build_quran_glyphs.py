"""Build the word table for Quran page fonts (King Fahd Complex `QCF_Pnnn`, `QCF2nnn`).

Usage:
    uv run python scripts/build_quran_glyphs.py

Each page font of the Madinah Mushaf (v1: 1405H print, v2: 1421H print) draws one glyph
per word of that page on Presentation Forms-A code points. The Quran.com API gives every
word's glyph codes and page in both prints, and its text. The table keeps the words in
Quran order without diacritics or pause marks and, per print, each word's page and glyph
codes (a word with a pause mark has two glyphs).

Writes src/harfix/data/quran_glyphs.json.gz.
"""

from __future__ import annotations

import gzip
import json
import re
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
URL = (
    "https://api.quran.com/api/v4/verses/by_page/{page}?words=true&per_page=50&page={n}"
    "&word_fields=code_v1,code_v2,v1_page,v2_page,text_imlaei"
)
# Harakat, tanween, shadda, sukun, superscript alef, Quranic pause and annotation marks.
_MARKS = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]")


def fetch() -> list[dict]:
    words = []
    for page in range(1, 605):
        n = 1
        while True:
            request = urllib.request.Request(
                URL.format(page=page, n=n), headers={"User-Agent": "harfix-build/1"}
            )
            data = json.load(urllib.request.urlopen(request, timeout=60))
            for verse in data["verses"]:
                words += verse["words"]
            if not data["pagination"]["next_page"]:
                break
            n += 1
        time.sleep(0.1)
    return words


def main() -> None:
    words = fetch()
    payload: dict = {
        "format": 1,
        "source": "Quran.com API v4 (code_v1, code_v2, v1_page, v2_page, text_imlaei)",
        "text": [" ".join(_MARKS.sub("", w["text_imlaei"]).split()) for w in words],
    }
    for version in ("v1", "v2"):
        # Pages run in Quran order: the index of each page's first word, then every
        # word's glyph codes.
        pages = [w[f"{version}_page"] for w in words]
        payload[version] = {
            "first_word": [pages.index(p) for p in range(1, 605)],
            "codes": " ".join(w[f"code_{version}"] for w in words),
        }
    path = ROOT / "src" / "harfix" / "data" / "quran_glyphs.json.gz"
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, separators=(",", ":"))
    print(path, path.stat().st_size, "bytes")


if __name__ == "__main__":
    main()
