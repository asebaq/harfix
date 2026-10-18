"""Learn font maps for pre-Unicode Arabic fonts from typed editions; evaluate and export.

Usage:
    uv run --group decoder python scripts/train_font_maps.py --train 9 10 \
        --test 18 1576 --save src/harfix/data/font_maps.json.gz

Pages are read into symbols by `harfix.decode.glyph_lines`. Shamela's typed text of the
same printed page gives the letters (training pages are matched through the page numbers
drawn on them). EM over a monotone alignment learns, per symbol, the probability of
producing nothing (diacritics, elongation), one letter, or a two-letter ligature; insertions
absorb typed text the page does not draw. The exported map is decoded exactly as
`harfix decode` does (`harfix.decode.decode_line`), so the scores below are the shipped
decoder's.

Results: reports/font_decoder.md. Needs the Shamela corpus (scripts/benchmark.py
fetch-text) and, for the OCR baseline, archive.org's `*_hocr_searchtext.txt.gz` and
`*_hocr_pageindex.json.gz` for each PDF in corpus/ocr/.
"""

from __future__ import annotations

import argparse
import datetime as dt
import gzip
import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from pdfminer.high_level import extract_pages
from scipy.signal import lfilter

from harfix.decode import SPACE, FontMap, decode_line, glyph_lines, is_gap
from harfix.model import default_models
from harfix.normalize import letters_only

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "corpus" / "shamela_text"
_ARABIC = re.compile(r"[\u0600-\u06FF\uFB50-\uFDFF\uFE70-\uFEFF]")


# ---------------------------------------------------------------- pages


def printed_numbers(lines: list[list[str]]) -> set[int]:
    """Candidate page numbers: a font whose only glyphs on the page are 1-4 digits, read
    in either direction (visual order draws digits left to right)."""
    by_font: dict[str, str] = defaultdict(str)
    for line in lines:
        for s in line:
            if not is_gap(s):
                font, char = s.split(":", 1)
                by_font[font] += char
    out = set()
    for text in by_font.values():
        if text.isdigit() and len(text) <= 4:
            out |= {int(text), int(text[::-1])}
    return out


def pdf_pages(pdf: Path, pages: list[int]) -> dict[int, list[list[str]]]:
    out = {}
    for number, layout in zip(
        pages, extract_pages(str(pdf), page_numbers=[p - 1 for p in pages]), strict=True
    ):
        out[number] = glyph_lines(layout)
    return out


# ---------------------------------------------------------------- typed text


def typed_pages(book: str) -> dict[int, str]:
    path = CORPUS / "text" / f"{book}.jsonl"
    if not path.exists():
        # Shamela's typed edition, with the printed page number of every page.
        from benchmark import _fetch_book  # scripts/ is on sys.path when run as a script

        _fetch_book(book, path)
    pages: dict[int, list[str]] = defaultdict(list)
    for line in path.open(encoding="utf-8"):
        record = json.loads(line)
        if record.get("printed") is not None:
            pages[int(record["printed"])].append(record["text"])
    return {p: letters_only("\n".join(t).replace("\r", "\n")) for p, t in pages.items()}


def page_offset(pdf_lines: dict[int, list[list[str]]]) -> int | None:
    """Most common difference between PDF page index and printed page number."""
    diffs = Counter(
        index - number for index, lines in pdf_lines.items() for number in printed_numbers(lines)
    )
    return diffs.most_common(1)[0][0] if diffs else None


# ---------------------------------------------------------------- model


class Model:
    """p(output | symbol) for outputs: nothing, one letter, or a two-letter ligature."""

    def __init__(self, alphabet: str, pairs: list[str]):
        self.alphabet = alphabet
        self.pairs = pairs
        self.letter = {c: i for i, c in enumerate(alphabet)}
        self.pair = {p: i for i, p in enumerate(pairs)}
        self.symbols: dict[str, int] = {}
        self.e0 = np.zeros(0)
        self.e1 = np.zeros((0, len(alphabet)))
        self.e2 = np.zeros((0, len(pairs)))
        self.insert = 0.02

    def add_symbols(self, symbols):
        new = [s for s in dict.fromkeys(symbols) if s not in self.symbols]
        for s in new:
            self.symbols[s] = len(self.symbols)
        if not new:
            return
        k = len(new)
        e0 = np.full(k, 0.2)
        e1 = np.full((k, len(self.alphabet)), 0.6 / len(self.alphabet))
        e2 = np.full((k, len(self.pairs)), 0.2 / max(1, len(self.pairs)))
        for row, s in enumerate(new):
            if s in (SPACE, "gap:wide", "gap:narrow"):
                e1[row] = 0.01 / len(self.alphabet)
                e1[row, self.letter[SPACE]] = 0.9 if s != "gap:narrow" else 0.5
        self.e0 = np.concatenate([self.e0, e0])
        self.e1 = np.vstack([self.e1, e1])
        self.e2 = np.vstack([self.e2, e2])

    def _pass(self, sym: list[int], let: np.ndarray, pair_idx: np.ndarray):
        """Forward-backward over the monotone alignment; returns expected counts."""
        n, m = len(sym), len(let)
        p1 = self.e1[sym][:, let]  # (n, m): symbol i emits letter j
        p2 = np.zeros((n, m))
        valid = pair_idx >= 0
        p2[:, valid] = self.e2[sym][:, pair_idx[valid]]  # symbol i emits letters j-1, j
        p0 = self.e0[sym]
        ins = self.insert

        def ins_fwd(row):  # g[j] = row[j] + ins * g[j-1]: letters typed but not drawn
            return lfilter([1.0], [1.0, -ins], row)

        def ins_bwd(row):  # h[j] = row[j] + ins * h[j+1]
            return lfilter([1.0], [1.0, -ins], row[::-1])[::-1]

        # alpha[i]: after symbol i-1's emission and the insertions that follow it,
        # scaled by c[0..i]. beta_pre[i]: backward vector before row i's insertions.
        alpha = np.zeros((n + 1, m + 1))
        c = np.zeros(n + 1)
        start = np.zeros(m + 1)
        start[0] = 1.0
        row = ins_fwd(start)
        c[0] = row.sum()
        alpha[0] = row / c[0]
        for i in range(n):
            a = alpha[i]
            row = a * p0[i]
            row[1:] += a[:-1] * p1[i]
            row[2:] += a[:-2] * p2[i, 1:]
            row = ins_fwd(row)
            total = row.sum()
            if not total > 0:
                return None  # no monotone alignment of this page to its typed text
            c[i + 1] = total
            alpha[i + 1] = row / total
        p_hat = alpha[n, m]
        if not p_hat > 0:
            return None

        beta_pre = np.zeros((n + 1, m + 1))
        end = np.zeros(m + 1)
        end[m] = 1.0
        beta_pre[n] = ins_bwd(end)
        for i in range(n - 1, -1, -1):
            b = beta_pre[i + 1]
            row = b * p0[i]
            row[:-1] += b[1:] * p1[i]
            row[:-2] += b[2:] * p2[i, 1:]
            beta_pre[i] = ins_bwd(row / c[i + 1])

        c0 = np.zeros(len(self.symbols))
        c1 = np.zeros_like(self.e1)
        c2 = np.zeros_like(self.e2)
        idx = pair_idx[1:]
        ok = idx >= 0
        for i in range(n):
            s = sym[i]
            a, b = alpha[i], beta_pre[i + 1]
            z = c[i + 1] * p_hat
            c0[s] += (a * p0[i] * b).sum() / z
            np.add.at(c1[s], let, a[:-1] * p1[i] * b[1:] / z)
            np.add.at(c2[s], idx[ok], (a[:-2] * p2[i, 1:] * b[2:])[ok] / z)
        loglik = float(np.log(c).sum() + np.log(p_hat))
        if not (np.isfinite(loglik) and np.isfinite(c0).all()):
            return None
        return c0, c1, c2, loglik

    def train(self, examples, iterations: int = 8) -> list[float]:
        history = []
        for _ in range(iterations):
            c0 = np.zeros(len(self.symbols))
            c1 = np.zeros_like(self.e1)
            c2 = np.zeros_like(self.e2)
            total = 0.0
            for sym, let, pair_idx in examples:
                result = self._pass(sym, let, pair_idx)
                if result is None:
                    continue
                a, b, c, ll = result
                c0 += a
                c1 += b
                c2 += c
                total += ll
            norm = c0 + c1.sum(1) + c2.sum(1) + 1e-9
            self.counts = norm
            self.e0 = (c0 + 1e-4) / (norm + 1e-4 * (1 + c1.shape[1] + c2.shape[1]))
            self.e1 = (c1 + 1e-4) / (norm + 1e-4 * (1 + c1.shape[1] + c2.shape[1]))[:, None]
            self.e2 = (c2 + 1e-4) / (norm + 1e-4 * (1 + c1.shape[1] + c2.shape[1]))[:, None]
            history.append(total)
        return history

    def to_font_map(self, metadata: dict, min_count: float = 3.0, k: int = 4) -> FontMap:
        """Each symbol seen at least `min_count` times (in expectation), with its k most
        likely outputs, for legacy font families only: families whose glyphs extract as
        non-Arabic characters and of which at least 30% decode to Arabic letters. Unicode
        Arabic fonts and Latin fonts on the same pages are left out, so their pages are
        never decoded."""
        outputs: dict[str, list[tuple[str, float]]] = {}
        for s, i in self.symbols.items():
            if self.counts[i] < min_count:
                continue
            cands = [(self.e0[i], "")]
            cands += [(p, self.alphabet[j]) for j, p in enumerate(self.e1[i])]
            cands += [(p, self.pairs[j]) for j, p in enumerate(self.e2[i])]
            cands.sort(reverse=True)
            outputs[s] = [(out, float(np.log(p))) for p, out in cands[:k] if p > 1e-3]
        unicode_arabic: set[str] = set()
        decodes_to_arabic: dict[str, list[bool]] = defaultdict(list)
        for s, opts in outputs.items():
            if is_gap(s):
                continue
            family, char = s.split(":", 1)
            if _ARABIC.search(char):
                unicode_arabic.add(family)
            decodes_to_arabic[family].append(bool(_ARABIC.search(opts[0][0])))
        legacy = {
            f
            for f, flags in decodes_to_arabic.items()
            if f not in unicode_arabic and sum(flags) >= 0.3 * len(flags)
        }
        outputs = {s: o for s, o in outputs.items() if is_gap(s) or s.split(":", 1)[0] in legacy}
        return FontMap(outputs, {**metadata, "families": sorted(legacy)})


def example(model: Model, lines: list[list[str]], letters: str):
    symbols = [s for line in lines for s in [*line, SPACE]]
    model.add_symbols(symbols)
    sym = [model.symbols[s] for s in symbols]
    let = np.array([model.letter[c] for c in letters])
    pair_idx = np.full(len(letters), -1)
    for j in range(1, len(letters)):
        pair_idx[j] = model.pair.get(letters[j - 1 : j + 1], -1)
    return sym, let, pair_idx


# ---------------------------------------------------------------- evaluation


def word_scores(decoded: str, truth: str) -> tuple[float, float]:
    """(precision, recall) of decoded words against the typed page, as multisets."""
    d = Counter(w for w in letters_only(decoded).split() if len(w) >= 2)
    t = Counter(w for w in truth.split() if len(w) >= 2)
    hit = sum((d & t).values())
    return (hit / sum(d.values()) if d else 0.0, hit / sum(t.values()) if t else 0.0)


def _manifest_entry(book: str) -> tuple[Path, dict]:
    for manifest in sorted((ROOT / "corpus").glob("shamela*/manifest.jsonl")):
        for line in manifest.open(encoding="utf-8"):
            entry = json.loads(line)
            if str(entry["book_id"]) == book:
                return manifest.parent, entry
    raise SystemExit(f"book {book} is not in any corpus/shamela*/manifest.jsonl")


def load(book: str):
    """PDF glyph lines by page, typed pages by printed number, and the page offset read
    from printed page numbers (None if none were found)."""
    folder, entry = _manifest_entry(book)
    pdf = folder / entry["file"]
    from pdfminer.pdfdocument import PDFDocument
    from pdfminer.pdfpage import PDFPage
    from pdfminer.pdfparser import PDFParser

    with pdf.open("rb") as fh:
        count = sum(1 for _ in PDFPage.create_pages(PDFDocument(PDFParser(fh))))
    lines = pdf_pages(pdf, list(range(1, count + 1)))
    return lines, typed_pages(book), page_offset(lines)


def paired(lines, typed, offset) -> dict[int, tuple[list[list[str]], str]]:
    if offset is None:
        return {}
    return {
        index: (page_lines, typed[index - offset])
        for index, page_lines in lines.items()
        if page_lines and index - offset in typed
    }


def argmax_decode(font_map: FontMap, lines: list[list[str]]) -> str:
    return "\n".join(
        "".join(font_map.outputs[s][0][0] for s in line if s in font_map.outputs) for line in lines
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train", nargs="+", required=True, help="Shamela book ids")
    parser.add_argument("--test", nargs="*", default=[], help="books to score")
    parser.add_argument("--iterations", type=int, default=8)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--save", type=Path, help="write the learned font map here")
    args = parser.parse_args()

    books = {b: load(b) for b in set(args.train) | set(args.test)}
    pairs = {b: paired(*books[b]) for b in args.train}
    for b in args.train:
        print(f"book {b}: {len(pairs[b])} PDF pages matched to typed pages")

    # A book in both lists is split: half of its pages train, the other half are scored.
    rng = random.Random(args.seed)
    held_out: dict[str, set[int]] = {}
    for b in set(args.train) & set(args.test):
        pages = sorted(pairs[b])
        rng.shuffle(pages)
        held_out[b] = set(pages[: len(pages) // 2])

    training = [
        (lines, letters)
        for b in args.train
        for index, (lines, letters) in pairs[b].items()
        if index not in held_out.get(b, set())
    ]
    letter_pairs = Counter(
        letters[j : j + 2]
        for _, letters in training
        for j in range(len(letters) - 1)
        if SPACE not in letters[j : j + 2]
    )
    alphabet = "".join(sorted({c for b in books.values() for t in b[1].values() for c in t}))
    model = Model(alphabet, [p for p, _ in letter_pairs.most_common(150)])
    examples = [example(model, lines, letters) for lines, letters in training]
    print(f"training on {len(examples)} pages, {len(model.symbols)} symbols")
    history = model.train(examples, args.iterations)
    print("log-likelihood:", [round(h) for h in history])
    font_map = model.to_font_map(
        {
            "trained_on_shamela_books": sorted(args.train, key=int),
            "pages": len(examples),
            "date": dt.date.today().isoformat(),
        }
    )
    print(f"font map: {len(font_map.outputs)} symbols, families {font_map.metadata['families']}")
    if args.save:
        font_map.save(args.save)

    lm = default_models().spaced
    for b in args.test:
        lines, typed, _ = books[b]
        if b not in held_out:
            # An unseen book's typed text is only used for scoring: line its pages up with
            # the decoded text, since printed page numbers may be missing or misread.
            sample = sorted(i for i in lines if lines[i])[::5]
            quick = {i: argmax_decode(font_map, lines[i]) for i in sample}
            offset = max(
                range(-40, 41),
                key=lambda d: sum(word_scores(quick[i], typed.get(i - d, ""))[1] for i in sample),
            )
            pairs[b] = paired(lines, typed, offset)
        pages = pairs[b]
        chosen = sorted(held_out.get(b, set(pages)))
        if not chosen:
            print(f"book {b}: no pages to score")
            continue
        kind = "held-out pages" if b in held_out else "unseen book"
        known = np.mean([font_map.known_share(pages[i][0]) for i in chosen])
        for label, decode in (
            ("symbol argmax", lambda ls: argmax_decode(font_map, ls)),
            ("harfix decode", lambda ls: "\n".join(decode_line(x, font_map, lm) for x in ls)),
        ):
            decoded = {i: decode(pages[i][0]) for i in chosen}
            scores = [word_scores(decoded[i], pages[i][1]) for i in chosen]
            print(
                f"book {b} ({kind}, {len(scores)} pages, glyphs known {known:.0%}, {label}): "
                f"word precision {np.mean([s[0] for s in scores]):.1%}, "
                f"recall {np.mean([s[1] for s in scores]):.1%}"
            )
        ocr = ocr_pages(b)
        if ocr:
            # Archive.org's page list can be shifted against the PDF: use the best shift.
            best = max(
                range(-3, 4),
                key=lambda d: sum(word_scores(ocr.get(i + d, ""), pages[i][1])[1] for i in chosen),
            )
            scores = [word_scores(ocr.get(i + best, ""), pages[i][1]) for i in chosen]
            print(
                f"book {b} ({kind}, {len(scores)} pages, archive.org OCR): "
                f"word precision {np.mean([s[0] for s in scores]):.1%}, "
                f"recall {np.mean([s[1] for s in scores]):.1%}"
            )


def ocr_pages(book: str) -> dict[int, str]:
    """archive.org's OCR of the PDF, by 1-based page, if downloaded into corpus/ocr."""
    _, entry = _manifest_entry(book)
    # archive.org names derived OCR files after the PDF, which may differ from the item.
    base = ROOT / "corpus" / "ocr" / Path(entry["url"]).stem
    index_path = Path(f"{base}_hocr_pageindex.json.gz")
    text_path = Path(f"{base}_hocr_searchtext.txt.gz")
    if not index_path.exists() or not text_path.exists():
        return {}
    index = json.loads(gzip.decompress(index_path.read_bytes()))
    text = gzip.decompress(text_path.read_bytes()).decode("utf-8")
    return {i + 1: text[start:end] for i, (start, end, *_) in enumerate(index)}


if __name__ == "__main__":
    main()
