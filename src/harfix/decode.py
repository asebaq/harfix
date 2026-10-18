"""Decode pre-Unicode Arabic fonts from their glyphs, without OCR.

Old desktop-publishing fonts (the `AXt…` / `Adv…` families) put Arabic glyphs on ASCII
codes and split one word's glyphs over several font subsets, so the text layer extracts
as gibberish in a scrambled order. Here a page is read as positioned glyphs across all
fonts, grouped into lines by baseline and ordered right to left. Each glyph becomes a
symbol `font family:extracted character`, and a learned font map gives each symbol's
likely outputs: nothing (diacritics, elongation strokes), one letter, or a two-letter
ligature. A beam search picks the outputs that read best under harfix's letter model.

A page is decoded only when the map knows nearly all of its glyphs, and the result is
trusted only when harfix's own check passes it. Font maps are learned by
`scripts/train_font_maps.py` from typed editions of the same books.
"""

from __future__ import annotations

import gzip
import json
import math
import re
import statistics
from collections import Counter, defaultdict
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from pathlib import Path

from pdfminer.high_level import extract_pages
from pdfminer.layout import LTChar, LTContainer

from .detect import Assessment, assess_text
from .model import CharLM, default_models

SPACE = " "
GAP_WIDE = "gap:wide"
GAP_NARROW = "gap:narrow"
_SUBSET = re.compile(r"^[A-Z]{6}\+")
_LONE_ARTICLE = re.compile(r"(?<!\S)ال +(?=\S)")
# Decode a page only when the font map knows this share of its glyphs. Whether the result
# is trusted is then up to harfix's check of the decoded text.
MIN_KNOWN = 0.8


# ---------------------------------------------------------------- glyph streams


def _chars(container: LTContainer) -> Iterator[LTChar]:
    for item in container:
        if isinstance(item, LTChar):
            if item.get_text().strip():
                yield item
        elif isinstance(item, LTContainer):
            yield from _chars(item)


def glyph_lines(layout: LTContainer) -> list[list[str]]:
    """A page's glyphs as lines of symbols, top to bottom, each line right to left."""
    chars = list(_chars(layout))
    if not chars:
        return []
    size = statistics.median(c.size for c in chars)
    counts = Counter(round(c.matrix[5]) for c in chars)
    # Body lines are baselines carrying many glyphs; diacritics sit on nearby offsets.
    peaks: list[int] = []
    for y, n in counts.most_common():
        if n < 6:
            break
        if all(abs(y - p) > 0.9 * size for p in peaks):
            peaks.append(y)
    if not peaks:
        return []
    lines: dict[int, list[LTChar]] = defaultdict(list)
    for c in chars:
        lines[min(peaks, key=lambda p: abs(p - c.matrix[5]))].append(c)
    out = []
    for y in sorted(lines, reverse=True):
        row = sorted(lines[y], key=lambda c: -(c.x0 + c.x1) / 2)
        # Gaps come from glyphs on the body baseline only (marks on other offsets sit over
        # them), as two symbols by width: spaces between words, or the gap after a letter
        # that does not join inside a word. The font map learns which is which.
        body = [c for c in row if abs(c.matrix[5] - y) < 1]
        cuts = sorted(
            (
                ((a.x0 + b.x1) / 2, GAP_WIDE if a.x0 - b.x1 > 0.28 * size else GAP_NARROW)
                for a, b in zip(body, body[1:], strict=False)
                if a.x0 - b.x1 > 0.15 * size
            ),
            reverse=True,
        )
        symbols = []
        for c in row:
            while cuts and (c.x0 + c.x1) / 2 < cuts[0][0]:
                symbols.append(cuts.pop(0)[1])
            symbols.append(_SUBSET.sub("", c.fontname) + ":" + c.get_text())
        out.append(symbols)
    return out


def is_gap(symbol: str) -> bool:
    return symbol in (SPACE, GAP_WIDE, GAP_NARROW)


# ---------------------------------------------------------------- font maps


@dataclass
class FontMap:
    """Each symbol's likely outputs with their log probabilities."""

    outputs: dict[str, list[tuple[str, float]]]
    metadata: dict

    def known_share(self, lines: list[list[str]]) -> float:
        glyphs = [s for line in lines for s in line if not is_gap(s)]
        return sum(s in self.outputs for s in glyphs) / len(glyphs) if glyphs else 0.0

    def save(self, path: Path) -> None:
        payload = {
            "format": 1,
            "metadata": self.metadata,
            "outputs": {s: [[o, round(p, 4)] for o, p in opts] for s, opts in self.outputs.items()},
        }
        with gzip.open(path, "wt", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, separators=(",", ":"), sort_keys=True)

    @classmethod
    def load(cls, path: Path) -> FontMap:
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            data = json.load(fh)
        outputs = {s: [(o, p) for o, p in opts] for s, opts in data["outputs"].items()}
        return cls(outputs, data.get("metadata", {}))


@lru_cache(maxsize=1)
def default_font_map() -> FontMap:
    with resources.as_file(resources.files("harfix") / "data" / "font_maps.json.gz") as path:
        return FontMap.load(path)


# ---------------------------------------------------------------- decoding


def decode_line(
    line: Iterable[str],
    font_map: FontMap,
    lm: CharLM,
    *,
    weight: float = 0.6,
    bonus: float = 1.5,
    beam: int = 8,
) -> str:
    """Most likely letters for one line of symbols: outputs scored by the letter model."""
    order = lm.order - 1
    hyps = [(0.0, SPACE * order, "")]  # (score, letter-model context, text)
    for symbol in [*line, SPACE]:
        options = font_map.outputs.get(symbol, [("", 0.0)])
        expanded: dict[tuple[str, str], tuple[float, str, str]] = {}
        for score, ctx, text in hyps:
            for out, logp in options:
                new_score, new_ctx, new_text = score + logp, ctx, text
                for ch in out:
                    if ch == SPACE and new_ctx.endswith(SPACE):
                        continue
                    new_score += weight * math.log(lm.prob(ch, new_ctx)) + bonus
                    new_ctx = (new_ctx + ch)[-order:]
                    new_text += ch
                key = (new_ctx, new_text[-12:])
                if key not in expanded or expanded[key][0] < new_score:
                    expanded[key] = (new_score, new_ctx, new_text)
        hyps = sorted(expanded.values(), reverse=True)[:beam]
    # The article never stands alone; a gap after it is the font's spacing.
    return _LONE_ARTICLE.sub("ال", hyps[0][2].strip())


@dataclass
class DecodedPage:
    page: int
    text: str
    # Share of the page's glyphs the font map knows.
    known_share: float
    # harfix's check of the decoded text; None when the page was not decoded.
    assessment: Assessment | None

    @property
    def trusted(self) -> bool:
        a = self.assessment
        return a is not None and a.sufficient and a.route in ("keep", "repair")

    def to_dict(self) -> dict:
        return {
            "page": self.page,
            "trusted": self.trusted,
            "known_share": round(self.known_share, 4),
            "assessment": self.assessment.to_dict() if self.assessment else None,
            "text": self.text,
        }


def decode_pdf(
    path: str | Path,
    *,
    pages: Iterable[int] | None = None,
    font_map: FontMap | None = None,
) -> list[DecodedPage]:
    """Decode the requested 1-based pages whose glyphs the font map knows."""
    font_map = font_map or default_font_map()
    lm = default_models().spaced
    page_numbers = sorted({p - 1 for p in pages}) if pages is not None else None
    out = []
    for index, layout in enumerate(extract_pages(str(path), page_numbers=page_numbers)):
        number = page_numbers[index] + 1 if page_numbers is not None else index + 1
        lines = glyph_lines(layout)
        known = font_map.known_share(lines)
        if known < MIN_KNOWN:
            out.append(DecodedPage(number, "", known, None))
            continue
        text = "\n".join(decode_line(line, font_map, lm) for line in lines)
        out.append(DecodedPage(number, text, known, assess_text(text)))
    return out
