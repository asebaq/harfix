"""Decode Arabic fonts without a usable Unicode map from their glyphs, without OCR.

Two kinds of font are decoded:

- Old desktop-publishing fonts (the `AXt…` / `Adv…` families) put Arabic glyphs on ASCII
  codes and split one word's glyphs over several font subsets, so the text layer extracts
  as gibberish in a scrambled order. A learned font map gives each glyph's likely outputs:
  nothing (diacritics, elongation strokes), one letter, or a two-letter ligature, and a
  beam search picks the outputs that read best under harfix's letter model. Font maps are
  learned by `scripts/train_font_maps.py` from typed editions of the same books.
- Fonts without a Unicode map whose glyphs carry Arabic names (`qafisolated`,
  `lamwithalef`) in the PDF's font encoding: the names spell the letters.

A page is read as positioned glyphs across all fonts, grouped into lines by baseline and
ordered right to left. Each glyph becomes a symbol `font family:extracted character`, or
`name:glyph name` for a named glyph. Glyphs of other fonts on the same page (Unicode
headings, page numbers) are kept as they are. A page is decoded only when it has glyphs
to decode and nearly all of its glyphs can be read, and the result is trusted only when
harfix's own check passes it.
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
from functools import cached_property, lru_cache
from importlib import resources
from pathlib import Path

from pdfminer.converter import PDFPageAggregator
from pdfminer.layout import LAParams, LTChar, LTContainer
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfinterp import PDFPageInterpreter, PDFResourceManager
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfparser import PDFParser
from pdfminer.pdftypes import PDFStream, resolve1

from .detect import Assessment, assess_text
from .glyphnames import fix_allah, glyph_letters
from .model import CharLM, default_models
from .normalize import decompose_presentation_forms
from .repair import _LTR_RUN

SPACE = " "
GAP_WIDE = "gap:wide"
GAP_NARROW = "gap:narrow"
NAMED = "name:"
QURAN = "quran:"
_EXACT = (NAMED, QURAN)
# Family of a kept font's glyphs once harfix has rejected that font's text.
UNREADABLE = "unreadable"
_SUBSET = re.compile(r"^[A-Z]{6}\+")
_CID = re.compile(r"\(cid:(\d+)\)")
_ARABIC_LETTER = re.compile(r"[\u0621-\u064A]")
_LONE_ARTICLE = re.compile(r"(?<!\S)ال +(?=\S)")
# Decode a page only when this share of its glyphs can be read (decoded or kept as they
# are), and this share needs decoding through the map, or this many glyphs are read
# exactly. Whether the result is trusted is then up to harfix's check of the decoded text.
MIN_KNOWN = 0.8
MIN_DECODED = 0.3
MIN_EXACT = 5
_PLAIN_GAPS = {
    SPACE: [(SPACE, 0.0)],
    GAP_WIDE: [(SPACE, 0.0)],
    GAP_NARROW: [("", -0.3), (SPACE, -1.5)],
}


# ---------------------------------------------------------------- glyph streams


def _chars(container: LTContainer) -> Iterator[LTChar]:
    for item in container:
        if isinstance(item, LTChar):
            if item.get_text().strip():
                yield item
        elif isinstance(item, LTContainer):
            yield from _chars(item)


def glyph_lines(
    layout: LTContainer, glyph_names: dict[str, dict[int, str]] | None = None
) -> list[list[str]]:
    """A page's glyphs as lines of symbols, top to bottom, each line right to left.
    `glyph_names` (from `font_glyph_names`) names the glyphs of a layout read by
    `_layouts`."""
    glyph_names = glyph_names or {}
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
            symbols.append(_symbol(c, glyph_names))
        out.append(symbols)
    return out


def _symbol(char: LTChar, glyph_names: dict[str, dict[int, str]]) -> str:
    text = char.get_text()
    if len(text) == 1 and _MARKER <= ord(text) < _MARKER + 256:
        return NAMED + glyph_names[char.fontname][ord(text) - _MARKER]
    family = _SUBSET.sub("", char.fontname)
    if m := _QURAN_FONT.fullmatch(family):
        return f"{QURAN}{'v2' if m.group(1) else 'v1'}:{int(m.group(2))}:{text}"
    return family + ":" + text


# King Fahd Complex page fonts of the Madinah Mushaf: `QCF_P063` (1405H print, v1) and
# `QCF2063` (1421H print, v2) each draw one glyph per word of that Mushaf page.
_QURAN_FONT = re.compile(r"QCF(2)?_?P?(\d{3})")


@lru_cache(maxsize=1)
def _quran_glyphs() -> dict[tuple[str, int], dict[str, str]]:
    """(print, page) to glyph to word; the second glyph of a word with a pause mark gives
    nothing."""
    path = resources.files("harfix") / "data" / "quran_glyphs.json.gz"
    if not path.is_file():
        return {}
    with resources.as_file(path) as file, gzip.open(file, "rt", encoding="utf-8") as fh:
        data = json.load(fh)
    table: dict[tuple[str, int], dict[str, str]] = {}
    for version in ("v1", "v2"):
        starts = [*data[version]["first_word"], len(data["text"])]
        codes = data[version]["codes"].split(" ")
        for page in range(1, len(starts)):
            glyphs = table.setdefault((version, page), {})
            for i in range(starts[page - 1], starts[page]):
                glyphs[codes[i][0]] = data["text"][i]
                glyphs.update(dict.fromkeys(codes[i][1:], ""))
    return table


def quran_table_available() -> bool:
    """Whether the Quran page-font table was built (`scripts/build_quran_glyphs.py`). It is
    not shipped yet: redistribution of the glyph-code data has not been cleared."""
    return bool(_quran_glyphs())


def quran_word(symbol: str) -> str | None:
    """The word a Quran page-font glyph draws, from `scripts/build_quran_glyphs.py`'s table.
    PDFs write the glyphs on their Presentation Forms-A code points, or on byte codes
    from 0x21 that count from the first of them (U+FB51 in v1, U+FC41 in v2)."""
    version, page, char = symbol[len(QURAN) :].split(":", 2)
    if len(char) == 1 and 0x21 <= ord(char) < 0x100:
        char = chr(ord(char) - 0x21 + (0xFB51 if version == "v1" else 0xFC41))
    return _quran_glyphs().get((version, int(page)), {}).get(char)


def _fonts(resources, seen: set[int]) -> Iterator[dict]:
    resources = resolve1(resources) or {}
    for font in (resolve1(resources.get("Font")) or {}).values():
        yield resolve1(font)
    for xobject in (resolve1(resources.get("XObject")) or {}).values():
        form = resolve1(xobject)
        if isinstance(form, PDFStream) and id(form) not in seen:
            seen.add(id(form))
            yield from _fonts(form.get("Resources"), seen)


def font_glyph_names(path: str | Path) -> dict[str, dict[int, str]]:
    """Per font name, code to glyph name for fonts whose encoding names Arabic glyphs
    (`qafisolated`, `lamwithalef`, `lamI`, `fnalef`). pdfminer cannot map these names, so
    without a Unicode map it extracts such glyphs as `(cid:N)` or as the base encoding's
    Latin character. Fonts that also carry a Unicode map are included: their maps are
    often partial or wrong where the names are right, and the names win."""
    out: dict[str, dict[int, str]] = {}
    with open(path, "rb") as fh:
        seen: set[int] = set()
        for page in PDFPage.create_pages(PDFDocument(PDFParser(fh))):
            for spec in _fonts(page.resources, seen):
                if not isinstance(spec, dict):
                    continue
                font = getattr(resolve1(spec.get("BaseFont")), "name", None)
                encoding = resolve1(spec.get("Encoding"))
                if not font or font in out or not isinstance(encoding, dict):
                    continue
                names, code = {}, 0
                for item in resolve1(encoding.get("Differences")) or []:
                    if isinstance(item, int):
                        code = item
                    elif hasattr(item, "name"):
                        if glyph_letters(item.name) is not None:
                            names[code] = item.name
                        code += 1
                # Signs and marks alone (`openparen`) do not make an Arabic font.
                letters = sum(1 for n in names.values() if _ARABIC_LETTER.search(glyph_letters(n)))
                out[font] = names if letters >= 5 else {}
    return {font: names for font, names in out.items() if names}


# Named glyphs are extracted as these private-use characters, one per code, so that two
# codes pdfminer would extract alike (a named `aleffinal` on code 32 and a real space)
# stay apart.
_MARKER = 0xF0000


class _NamedGlyphs(PDFResourceManager):
    def __init__(self, glyph_names: dict[str, dict[int, str]]) -> None:
        super().__init__()
        self._names = glyph_names

    def get_font(self, objid, spec):
        font = super().get_font(objid, spec)
        names = self._names.get(font.fontname)
        if names and not getattr(font, "_harfix_named", False):
            plain = font.to_unichr
            font.to_unichr = lambda cid: chr(_MARKER + cid) if cid in names else plain(cid)
            font._harfix_named = True
        return font


def _layouts(
    path: str | Path, page_numbers: list[int] | None, glyph_names: dict[str, dict[int, str]]
) -> Iterator[LTContainer]:
    manager = _NamedGlyphs(glyph_names)
    device = PDFPageAggregator(manager, laparams=LAParams())
    interpreter = PDFPageInterpreter(manager, device)
    with open(path, "rb") as fh:
        for page in PDFPage.get_pages(fh, pagenos=page_numbers):
            interpreter.process_page(page)
            yield device.get_result()


def is_gap(symbol: str) -> bool:
    return symbol in (SPACE, GAP_WIDE, GAP_NARROW)


# ---------------------------------------------------------------- font maps


@dataclass
class FontMap:
    """Each symbol's likely outputs with their log probabilities."""

    outputs: dict[str, list[tuple[str, float]]]
    metadata: dict

    @cached_property
    def families(self) -> frozenset[str]:
        """Font families the map decodes; glyphs of other fonts are kept as they are."""
        return frozenset(s.split(":", 1)[0] for s in self.outputs if not is_gap(s))

    def options(self, symbol: str, learned: bool = True) -> list[tuple[str, float]] | None:
        """A symbol's possible outputs, or None when it cannot be read. On a line without
        learned glyphs (`learned=False`) a gap is only a space or nothing: what the map
        learned about gaps belongs to its fonts."""
        if is_gap(symbol) and not learned:
            return _PLAIN_GAPS[symbol]
        if symbol in self.outputs:
            return self.outputs[symbol]
        if symbol.startswith(NAMED):
            letters = glyph_letters(symbol[len(NAMED) :])
            return [(letters, 0.0)] if letters is not None else None
        if symbol.startswith(QURAN):
            word = quran_word(symbol)
            # One glyph is one word: a space after it whatever the gaps say.
            return [(word + SPACE if word else "", 0.0)] if word is not None else None
        family, _, char = symbol.partition(":")
        if is_gap(symbol) or family in self.families or family == UNREADABLE:
            return None
        if _CID.search(char):
            return None
        return [(decompose_presentation_forms(char)[0], 0.0)]

    def kept_texts(self, lines: list[list[str]]) -> dict[str, str]:
        """Per font family whose glyphs would be kept as they are, its text on the page."""
        texts: dict[str, list[str]] = defaultdict(list)
        for line in lines:
            current: dict[str, list[str]] = defaultdict(list)
            for s in line:
                if is_gap(s):
                    for chars in current.values():
                        chars.append(" ")
                elif s not in self.outputs and not s.startswith(_EXACT) and self.options(s):
                    family, _, char = s.partition(":")
                    current[family].append(char)
            for family, chars in current.items():
                texts[family].append("".join(chars))
        return {family: "\n".join(rows) for family, rows in texts.items()}

    def coverage(self, lines: list[list[str]]) -> tuple[float, float, int]:
        """(share of glyphs that can be read, share that is decoded rather than kept,
        how many are read exactly: named glyphs and Quran page-font glyphs)."""
        glyphs = [s for line in lines for s in line if not is_gap(s)]
        if not glyphs:
            return 0.0, 0.0, 0
        known = [s for s in glyphs if self.options(s) is not None]
        exact = sum(1 for s in known if s.startswith(_EXACT))
        decoded = sum(1 for s in glyphs if s in self.outputs) + exact
        return len(known) / len(glyphs), decoded / len(glyphs), exact

    def wants_decoding(self, lines: list[list[str]]) -> bool:
        """Whether a page has glyphs to decode: a share learned through the map, or a few
        read exactly (a Quran quotation on an otherwise readable page)."""
        _, decoded, exact = self.coverage(lines)
        return decoded >= MIN_DECODED or exact >= MIN_EXACT

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


def mark_unreadable(lines: list[list[str]], rejected: set[str]) -> list[list[str]]:
    """The lines with the glyphs of rejected font families marked as unreadable."""
    if not rejected:
        return lines
    return [
        [f"{UNREADABLE}:{s}" if s.partition(":")[0] in rejected else s for s in line]
        for line in lines
    ]


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
    line = list(line)
    learned = any(s in font_map.outputs and not is_gap(s) for s in line)
    for symbol in [*line, SPACE]:
        options = font_map.options(symbol, learned) or [("", 0.0)]
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
    text = fix_allah(_LONE_ARTICLE.sub("ال", hyps[0][2].strip()))
    # Glyphs were read right to left; numbers and Latin words kept as they are read left
    # to right.
    return _LTR_RUN.sub(lambda m: m.group()[::-1], text)


@dataclass
class DecodedPage:
    page: int
    text: str
    # Share of the page's glyphs that can be read: decoded, or kept as they are because
    # their font has a Unicode map.
    known_share: float
    # Share of the page's glyphs decoded through a font map or glyph names.
    decoded_share: float
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
            "decoded_share": round(self.decoded_share, 4),
            "assessment": self.assessment.to_dict() if self.assessment else None,
            "text": self.text,
        }


def decode_pdf(
    path: str | Path,
    *,
    pages: Iterable[int] | None = None,
    font_map: FontMap | None = None,
) -> list[DecodedPage]:
    """Decode the requested 1-based pages that have glyphs to decode and can be read."""
    font_map = font_map or default_font_map()
    lm = default_models().spaced
    names = font_glyph_names(path)
    page_numbers = sorted({p - 1 for p in pages}) if pages is not None else None
    if page_numbers == []:
        return []
    numbers, pages_lines = [], []
    for index, layout in enumerate(_layouts(path, page_numbers, names)):
        numbers.append(page_numbers[index] + 1 if page_numbers is not None else index + 1)
        pages_lines.append(glyph_lines(layout, names))

    out = []
    for number, lines in zip(numbers, screen_kept_fonts(pages_lines, font_map), strict=True):
        known, decoded, _ = font_map.coverage(lines)
        if known < MIN_KNOWN or not font_map.wants_decoding(lines):
            out.append(DecodedPage(number, "", known, decoded, None))
            continue
        text = "\n".join(decode_line(line, font_map, lm) for line in lines)
        out.append(DecodedPage(number, text, known, decoded, assess_text(text)))
    return out


def screen_kept_fonts(pages: list[list[list[str]]], font_map: FontMap) -> list[list[list[str]]]:
    """The pages' lines with the glyphs of kept fonts that fail harfix's check (another
    legacy font, a wrong Unicode map) marked as unreadable. A font's runs too short to
    judge on their page are judged pooled across the pages, as in `scan`. Only pages with
    glyphs to decode are checked: the others are not decoded whatever their fonts."""
    kept = [font_map.kept_texts(lines) if font_map.wants_decoding(lines) else {} for lines in pages]
    short: dict[str, list[str]] = defaultdict(list)
    rejected_on: list[set[str]] = [set() for _ in pages]
    for rejected, texts in zip(rejected_on, kept, strict=True):
        for family, text in texts.items():
            verdict = assess_text(text, order_known=False)
            if not verdict.decisive:
                short[family].append(text)
            elif verdict.route == "ocr":
                rejected.add(family)
    pooled = {
        family
        for family, texts in short.items()
        if assess_text("\n".join(texts), order_known=False).route == "ocr"
    }
    return [
        mark_unreadable(lines, rejected | pooled)
        for lines, rejected in zip(pages, rejected_on, strict=True)
    ]
