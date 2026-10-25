"""Prototype: read glyphs of fonts with a wrong Unicode map by their outlines.

Usage:
    uv run --with fonttools --group extractors python scripts/outline_prototype.py

Every font in the corpus embeds a TrueType program (`FontFile2`) next to its ToUnicode
map. Each glyph's outline (decomposed, scaled to 1000 units per em) is hashed, and each
PDF votes for the text its map gives that outline. A glyph is read as the other PDFs read
it when at least 2 of them agree (60% of those that have it); the PDF's own book never
votes for itself. Two evaluations, as in `scripts/cipher_prototype.py`:

- runs: the benchmark font runs labelled broken (wrong letters, `same_script_substitution`)
  and clean controls, re-extracted with pdfminer with the other PDFs' readings, scored by
  the share of words found in Shamela's transcriptions;
- pages: all labelled benchmark pages through `harfix decode`, with fonts whose map the
  other PDFs contradict (>= 5 glyphs and >= 10% of the glyphs they agree on) read as named
  glyphs spelling the other PDFs' reading; baseline is `decode` as shipped.

Results and decision: reports/outline_prototype.md.
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
import pickle
import statistics
import sys
import unicodedata
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from functools import lru_cache
from pathlib import Path

from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.ttLib import TTFont
from pdfminer.converter import PDFPageAggregator
from pdfminer.layout import LAParams
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdffont import PDFCIDFont
from pdfminer.pdfinterp import PDFPageInterpreter, PDFResourceManager
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfparser import PDFParser
from pdfminer.pdftypes import resolve1

import harfix.decode as hd
from harfix.pdf import _collect_page

logging.getLogger("fontTools").setLevel(logging.ERROR)  # damaged subsets are common

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "corpus" / "shamela_text"
INDEX = ROOT / "build" / "outline_index.pkl"
BLANK = "blank"  # every glyph without contours shares one key
MIN_PDFS, MIN_SHARE = 2, 0.6
NAME_PREFIX = "outline."


# ---------------------------------------------------------------- index


def _outline_key(glyphset, name: str, upem: int) -> str:
    pen = DecomposingRecordingPen(glyphset)
    glyphset[name].draw(pen)
    if not pen.value:
        return BLANK
    s = 1000 / upem
    ops = [(op, tuple((round(x * s), round(y * s)) for x, y in args)) for op, args in pen.value]
    return hashlib.sha1(repr(ops).encode()).hexdigest()[:16]


def _gid(tt: TTFont, code: int, cid_font: bool) -> int | None:
    if cid_font:
        return code  # Identity CIDToGIDMap: every broken font in the benchmark has it
    order = tt.getGlyphOrder()
    for pid, eid, c in ((3, 0, 0xF000 | code), (3, 0, code), (1, 0, code), (3, 1, code)):
        table = tt["cmap"].getcmap(pid, eid) if "cmap" in tt else None
        if table and c in table.cmap:
            return order.index(table.cmap[c])
    return None


def _index_pdf(path: Path) -> tuple[str, dict]:
    """font name -> code -> (outline key, ToUnicode text), for embedded TrueType fonts."""
    out: dict = {}
    rm = PDFResourceManager()
    with path.open("rb") as fh:
        seen: set[int] = set()
        for page in PDFPage.create_pages(PDFDocument(PDFParser(fh))):
            for spec in hd._fonts(page.resources, seen):
                if not isinstance(spec, dict):
                    continue
                name = getattr(resolve1(spec.get("BaseFont")), "name", None)
                if not name or name in out or "ToUnicode" not in spec:
                    continue
                out[name] = {}
                desc = spec
                if getattr(resolve1(spec.get("Subtype")), "name", "") == "Type0":
                    desc = resolve1(resolve1(spec.get("DescendantFonts"))[0])
                program = (resolve1(desc.get("FontDescriptor")) or {}).get("FontFile2")
                if program is None:
                    continue
                try:
                    tt = TTFont(io.BytesIO(resolve1(program).get_data()), lazy=True)
                    font = rm.get_font(None, spec)
                    glyphset, order = tt.getGlyphSet(), tt.getGlyphOrder()
                    upem = tt["head"].unitsPerEm
                    cid = isinstance(font, PDFCIDFont)
                    umap = font.unicode_map.cid2unichr if font.unicode_map else {}
                    for code, text in umap.items():
                        gid = _gid(tt, code, cid)
                        if gid is not None and gid < len(order):
                            out[name][code] = (_outline_key(glyphset, order[gid], upem), text)
                except Exception:  # noqa: BLE001 - a damaged font program is left out
                    out[name] = {}
    return path.stem, {k: v for k, v in out.items() if v}


@lru_cache(maxsize=1)
def index() -> dict[str, dict]:
    """PDF stem -> font -> code -> (outline key, text); built once into build/."""
    if INDEX.exists():
        return pickle.loads(INDEX.read_bytes())
    pdfs = {}
    for p in sorted((ROOT / "corpus").glob("shamela*/*.pdf")):
        pdfs.setdefault(p.stem, p)
    with ProcessPoolExecutor() as pool:
        result = dict(pool.map(_index_pdf, pdfs.values()))
    INDEX.parent.mkdir(exist_ok=True)
    INDEX.write_bytes(pickle.dumps(result))
    return result


@lru_cache(maxsize=1)
def votes() -> dict[str, dict[str, Counter]]:
    """outline key -> PDF stem -> texts its map gives that outline."""
    out: dict = defaultdict(lambda: defaultdict(Counter))
    for stem, fonts in index().items():
        for codes in fonts.values():
            for key, text in codes.values():
                out[key][stem][unicodedata.normalize("NFKC", text)] += 1
    return out


def reading(stem: str, font: str) -> tuple[dict[int, str], int, set[int]]:
    """(code -> text, glyphs other PDFs agree on, codes where they contradict this map).
    Glyphs the other PDFs do not agree on keep this PDF's text."""
    out, agreed, contradicted = {}, 0, set()
    for code, (key, own) in index().get(stem, {}).get(font, {}).items():
        own = unicodedata.normalize("NFKC", own)
        others = Counter(t.most_common(1)[0][0] for s, t in votes()[key].items() if s != stem)
        text = own
        if others:
            best, n = others.most_common(1)[0]
            if n >= MIN_PDFS and n >= MIN_SHARE * sum(others.values()):
                agreed += 1
                if best != own:
                    contradicted.add(code)
                text = best
        out[code] = text
    return out, agreed, contradicted


# ---------------------------------------------------------------- runs


class _Override(PDFResourceManager):
    def __init__(self, tables: dict[str, dict[int, str]]) -> None:
        super().__init__()
        self.tables = tables

    def get_font(self, objid, spec):
        font = super().get_font(objid, spec)
        table = self.tables.get(font.fontname)
        if table and not getattr(font, "_outlines", False):
            plain = font.to_unichr
            font.to_unichr = lambda cid, t=table, p=plain: t[cid] if cid in t else p(cid)
            font._outlines = True
        return font


def _run_text(path: Path, pages: list[int], font: str, table: dict[int, str]) -> str:
    rm = _Override({font: table})
    device = PDFPageAggregator(rm, laparams=LAParams())
    interpreter = PDFPageInterpreter(rm, device)
    texts = []
    with path.open("rb") as fh:
        for page in PDFPage.get_pages(fh, pagenos=[p - 1 for p in pages]):
            interpreter.process_page(page)
            texts.append(_collect_page(device.get_result())[0].get(font, ""))
    return "\n".join(texts)


def _run_job(job):
    kind, book, font, path, pages = job
    table, _, contradicted = reading(path.stem, font)
    # Only the contradicted glyphs change: the others keep pdfminer's own reading.
    table = {code: table[code] for code in contradicted}
    before = _run_text(path, pages, font, {})
    after = _run_text(path, pages, font, table)
    return kind, book, font, before, after


def evaluate_runs(vocab) -> None:
    from cipher_prototype import _cases

    files, cases = _cases()
    jobs = [
        (v["kind"], book, font, files[book], sorted(v["pages"]))
        for (book, font), v in sorted(cases.items())
    ]
    with ProcessPoolExecutor() as pool:
        results = list(pool.map(_run_job, jobs))
    import benchmark

    rows = []
    print("| Run | Book | Font | Words | Found before | Found after |")
    print("|---|---|---|---:|---:|---:|")
    for kind, book, font, before, after in results:
        b, a = benchmark.label_run(before, vocab), benchmark.label_run(after, vocab)
        if b[1] < 20:
            continue
        rows.append((kind, b[2], a[2]))
        if kind == "broken" or abs(a[2] - b[2]) > 0.02:
            print(f"| {kind} | {book} | {font.split('+')[-1]} | {b[1]} | {b[2]:.0%} | {a[2]:.0%} |")
    print()
    for kind in ("broken", "clean"):
        r = [x for x in rows if x[0] == kind]
        print(
            f"{kind}: {len(r)} runs, median found {statistics.median(x[1] for x in r):.0%} -> "
            f"{statistics.median(x[2] for x in r):.0%}, worse by > 2 points "
            f"{sum(x[2] < x[1] - 0.02 for x in r)}, at >= 75% {sum(x[1] >= 0.75 for x in r)} -> "
            f"{sum(x[2] >= 0.75 for x in r)}"
        )


# ---------------------------------------------------------------- pages


_plain_letters = hd.glyph_letters
_plain_names = hd.font_glyph_names


def _letters(name: str) -> str | None:
    if name.startswith(NAME_PREFIX):
        return bytes.fromhex(name[len(NAME_PREFIX) :]).decode()
    return _plain_letters(name)


def _names(path: Path) -> dict[str, dict[int, str]]:
    """The PDF's glyph names, plus outline readings for fonts other PDFs contradict."""
    out = dict(_plain_names(path))
    for font in index().get(path.stem, {}):
        if font in out:
            continue
        table, agreed, contradicted = reading(path.stem, font)
        if len(contradicted) < max(5, 0.1 * agreed):
            continue
        if sum(1 for t in table.values() if hd._ARABIC_LETTER.search(t)) >= 5:
            out[font] = {
                code: NAME_PREFIX + ("" if t.isspace() else t).encode().hex()
                for code, t in table.items()
            }
    return out


def _page_job(job):
    path, pages, outlines = job
    if outlines:
        names = _names(path)
        hd.font_glyph_names = lambda _path, n=names: n
        hd.glyph_letters = _letters
    return [
        (p.page, p.assessment is not None, p.trusted, p.text)
        for p in hd.decode_pdf(path, pages=pages)
    ]


def evaluate_pages(vocab) -> None:
    import benchmark

    results = json.loads((CORPUS / "benchmark_runs.json").read_text(encoding="utf-8"))
    files = {}
    for line in (CORPUS / "manifest.jsonl").open(encoding="utf-8"):
        entry = json.loads(line)
        files["+".join(str(i) for i in entry["pdf_books"])] = CORPUS / entry["file"]
    labelled = [
        (
            r["book_id"],
            {p["page"]: p["label"] for p in r["pages"] if p["label"] in ("clean", "broken")},
        )
        for r in results
    ]
    labelled = [(b, ps) for b, ps in labelled if ps]
    tables = {}
    for outlines in (False, True):
        with ProcessPoolExecutor() as pool:
            out = list(
                pool.map(_page_job, [(files[b], sorted(ps), outlines) for b, ps in labelled])
            )
        table: Counter = Counter()
        for (_, labels), pages in zip(labelled, out, strict=True):
            for page, decoded, trusted, text in pages:
                if not decoded:
                    table[labels[page], "not decoded"] += 1
                elif not trusted:
                    table[labels[page], "not trusted"] += 1
                else:
                    table[labels[page], "trusted", benchmark.label_run(text, vocab)[0]] += 1
        tables[outlines] = table
    print("| Page label | Outcome | decode as shipped | with outline readings |")
    print("|---|---|---:|---:|")
    for key in sorted(set(tables[False]) | set(tables[True])):
        print(f"| {key[0]} | {' / '.join(key[1:])} | {tables[False][key]} | {tables[True][key]} |")


def main() -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import benchmark

    texts = sorted((CORPUS / "text").glob("*.jsonl"))
    typed = "\n".join(json.loads(line)["text"] for p in texts for line in p.open(encoding="utf-8"))
    vocab = benchmark.vocabulary(typed, None)
    fonts = sum(len(f) for f in index().values())
    glyphs = sum(len(c) for f in index().values() for c in f.values())
    print(f"index: {len(index())} PDFs, {fonts} fonts, {glyphs} glyphs\n")
    evaluate_runs(vocab)
    print()
    evaluate_pages(vocab)


if __name__ == "__main__":
    main()
