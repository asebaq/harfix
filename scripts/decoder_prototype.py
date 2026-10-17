"""Prototype: learn a pre-Unicode Arabic font's glyph-to-letter map from typed text.

Usage:
    uv run --group decoder python scripts/decoder_prototype.py --train 9 \
        --test 9 10 18 1576 --lm-weight 0.6 --letter-bonus 1.5

Each PDF page is read as positioned glyphs across all fonts (these fonts split one
word's glyphs over several font subsets), grouped into lines by baseline and ordered
right to left; gaps between glyphs become two gap symbols by width. Each glyph is a
symbol `font family:extracted character`. Shamela's typed text of the same printed page
gives the letters. EM over a monotone alignment learns, per symbol, the probability of
producing nothing (diacritics, elongation), one letter, or a two-letter ligature.
Decoding scores each symbol's likely outputs with harfix's letter model in a beam search.

Results and the go/no-go decision: reports/decoder_prototype.md. Needs the Shamela corpus
(scripts/benchmark.py) and, for the OCR baseline, archive.org's `*_hocr_searchtext.txt.gz`
and `*_hocr_pageindex.json.gz` for each PDF in corpus/ocr/.
"""

from __future__ import annotations

import argparse
import gzip
import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTChar, LTContainer
from scipy.signal import lfilter

from harfix.model import default_models
from harfix.normalize import letters_only

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "corpus" / "shamela_text"
SUBSET = re.compile(r"^[A-Z]{6}\+")
SPACE = " "


# ---------------------------------------------------------------- glyph streams


def _chars(container: LTContainer):
    for item in container:
        if isinstance(item, LTChar):
            if item.get_text().strip():
                yield item
        elif isinstance(item, LTContainer):
            yield from _chars(item)


def glyph_lines(layout) -> list[list[str]]:
    """Lines of symbols in reading order (top to bottom, right to left)."""
    chars = list(_chars(layout))
    if not chars:
        return []
    size = float(np.median([c.size for c in chars]))
    counts = Counter(round(c.matrix[5]) for c in chars)
    # Body lines: baselines carrying many glyphs. Diacritics sit on nearby offsets.
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
        # Word gaps come from glyphs on the body baseline only: diacritics and marks on
        # other offsets sit over the gaps and would hide them. Gaps are kept as two
        # symbols by width, so EM can learn which ones are spaces between words and which
        # follow letters that do not join (alef, dal, ra, waw) inside a word.
        body = [c for c in row if abs(c.matrix[5] - y) < 1]
        cuts = sorted(
            (
                ((a.x0 + b.x1) / 2, "gap:wide" if a.x0 - b.x1 > 0.28 * size else "gap:narrow")
                for a, b in zip(body, body[1:], strict=False)
                if a.x0 - b.x1 > 0.15 * size
            ),
            reverse=True,
        )
        symbols = []
        for c in row:
            while cuts and (c.x0 + c.x1) / 2 < cuts[0][0]:
                symbols.append(cuts.pop(0)[1])
            symbols.append(SUBSET.sub("", c.fontname) + ":" + c.get_text())
        out.append(symbols)
    return out


def printed_numbers(lines: list[list[str]]) -> set[int]:
    """Candidate page numbers: a font whose only glyphs on the page are 1-4 digits, read
    in either direction (visual order draws digits left to right)."""
    by_font: dict[str, str] = defaultdict(str)
    for line in lines:
        for s in line:
            if s != SPACE:
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
    pages: dict[int, list[str]] = defaultdict(list)
    for line in (CORPUS / "text" / f"{book}.jsonl").open(encoding="utf-8"):
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
            c[i + 1] = row.sum() or 1e-300
            alpha[i + 1] = row / c[i + 1]
        p_hat = alpha[n, m]
        if p_hat <= 0:
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
            self.e0 = (c0 + 1e-4) / (norm + 1e-4 * (1 + c1.shape[1] + c2.shape[1]))
            self.e1 = (c1 + 1e-4) / (norm + 1e-4 * (1 + c1.shape[1] + c2.shape[1]))[:, None]
            self.e2 = (c2 + 1e-4) / (norm + 1e-4 * (1 + c1.shape[1] + c2.shape[1]))[:, None]
            history.append(total)
        return history

    def decode_symbol(self, s: str) -> str:
        if s not in self.symbols:
            return ""
        i = self.symbols[s]
        options = [(self.e0[i], "")]
        j = int(self.e1[i].argmax())
        options.append((self.e1[i, j], self.alphabet[j]))
        if self.pairs:
            k = int(self.e2[i].argmax())
            options.append((self.e2[i, k], self.pairs[k]))
        return max(options)[1]

    def options(self, s: str, k: int = 4) -> list[tuple[float, str]]:
        """The k most likely outputs of a symbol with their log probabilities."""
        if s not in self.symbols:
            return [(0.0, "")]
        i = self.symbols[s]
        cands = [(self.e0[i], "")]
        cands += [(p, self.alphabet[j]) for j, p in enumerate(self.e1[i])]
        cands += [(p, self.pairs[j]) for j, p in enumerate(self.e2[i])]
        cands.sort(reverse=True)
        return [(float(np.log(p)), out) for p, out in cands[:k] if p > 1e-3]

    def decode(
        self,
        lines: list[list[str]],
        lm=None,
        weight: float = 1.0,
        bonus: float = 0.0,
        beam: int = 8,
    ) -> str:
        if lm is None:
            text = "\n".join("".join(self.decode_symbol(s) for s in line) for line in lines)
        else:
            text = "\n".join(self._beam(line, lm, weight, bonus, beam) for line in lines)
        # The article never stands alone; a gap after it is the font's spacing.
        return _LONE_ARTICLE.sub("ال", text)

    def _beam(self, line: list[str], lm, weight: float, bonus: float, beam: int) -> str:
        """Most likely letters for a line: symbol outputs scored with a character model."""
        order = lm.order - 1
        hyps = [(0.0, " " * order, "")]  # (score, LM context, text)
        for s in [*line, SPACE]:
            expanded: dict[tuple[str, str], tuple[float, str, str]] = {}
            for score, ctx, text in hyps:
                for logp, out in self.options(s):
                    new_score, new_ctx, new_text = score + logp, ctx, text
                    for ch in out:
                        if ch == SPACE and new_ctx.endswith(SPACE):
                            continue  # one boundary is enough
                        new_score += weight * np.log(lm.prob(ch, new_ctx)) + bonus
                        new_ctx = (new_ctx + ch)[-order:]
                        new_text += ch
                    key = (new_ctx, new_text[-12:])
                    if key not in expanded or expanded[key][0] < new_score:
                        expanded[key] = (new_score, new_ctx, new_text)
            hyps = sorted(expanded.values(), reverse=True)[:beam]
        return hyps[0][2].strip()


_LONE_ARTICLE = re.compile(r"(?<!\S)ال +(?=\S)")


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


def load(book: str):
    """PDF glyph lines by page, typed pages by printed number, and the page offset read
    from printed page numbers (None if none were found)."""
    manifest = [json.loads(line) for line in (CORPUS / "manifest.jsonl").open(encoding="utf-8")]
    pdf = CORPUS / next(b["file"] for b in manifest if str(b["book_id"]) == book)
    from pdfminer.pdfdocument import PDFDocument
    from pdfminer.pdfpage import PDFPage
    from pdfminer.pdfparser import PDFParser

    with pdf.open("rb") as fh:
        count = sum(1 for _ in PDFPage.create_pages(PDFDocument(PDFParser(fh))))
    lines = pdf_pages(pdf, list(range(1, count + 1)))
    return lines, typed_pages(book), page_offset(lines)


def paired(lines, typed, offset) -> dict[int, tuple[list[list[str]], str]]:
    return {
        index: (page_lines, typed[index - offset])
        for index, page_lines in lines.items()
        if page_lines and index - offset in typed
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train", nargs="+", required=True, help="Shamela book ids")
    parser.add_argument("--test", nargs="+", required=True)
    parser.add_argument("--iterations", type=int, default=8)
    parser.add_argument("--seed", type=int, default=0)
    # Chosen on book 9's held-out pages: see reports/decoder_prototype.md.
    parser.add_argument("--lm-weight", type=float, default=0.6)
    parser.add_argument("--letter-bonus", type=float, default=1.5)
    args = parser.parse_args()

    books = {b: load(b) for b in set(args.train) | set(args.test)}
    pairs = {b: paired(*books[b]) for b in args.train}
    for b in args.train:
        print(f"book {b}: {len(pairs[b])} PDF pages matched to typed pages")

    rng = random.Random(args.seed)
    held_out: dict[str, set[int]] = {}
    for b in args.train:
        pages = sorted(pairs[b])
        rng.shuffle(pages)
        held_out[b] = set(pages[: len(pages) // 2])

    letter_pairs = Counter()
    for b in args.train:
        for index, (_, letters) in pairs[b].items():
            if index not in held_out[b]:
                letter_pairs.update(
                    letters[j : j + 2]
                    for j in range(len(letters) - 1)
                    if SPACE not in letters[j : j + 2]
                )
    alphabet = "".join(sorted({c for b in books.values() for t in b[1].values() for c in t}))
    model = Model(alphabet, [p for p, _ in letter_pairs.most_common(150)])
    train = [
        example(model, lines, letters)
        for b in args.train
        for index, (lines, letters) in pairs[b].items()
        if index not in held_out[b]
    ]
    print(f"training on {len(train)} pages, {len(model.symbols)} symbols")
    history = model.train(train, args.iterations)
    print("log-likelihood:", [round(h) for h in history])

    for b in args.test:
        if b in pairs:
            continue
        # An unseen book's typed text is only used for scoring: line its pages up with the
        # decoded text itself, since printed page numbers may be missing or misread.
        lines, typed, _ = books[b]
        sample = sorted(i for i in lines if lines[i])[::5]
        quick = {i: model.decode(lines[i]) for i in sample}
        offset = max(
            range(-40, 41),
            key=lambda d: sum(word_scores(quick[i], typed.get(i - d, ""))[1] for i in sample),
        )
        pairs[b] = paired(lines, typed, offset)
        print(f"book {b}: {len(pairs[b])} PDF pages matched to typed pages (offset {offset})")

    lm = default_models().spaced
    for b in args.test:
        pages = pairs[b]
        chosen = sorted(held_out.get(b, set(pages)))
        kind = "held-out pages" if b in held_out else "unseen book"
        lm_args = {"lm": lm, "weight": args.lm_weight, "bonus": args.letter_bonus}
        for label, kwargs in (("symbol argmax", {}), ("with letter model", lm_args)):
            decoded = {i: model.decode(pages[i][0], **kwargs) for i in chosen}
            scores = [word_scores(decoded[i], pages[i][1]) for i in chosen]
            precision = float(np.mean([s[0] for s in scores]))
            recall = float(np.mean([s[1] for s in scores]))
            print(
                f"book {b} ({kind}, {len(scores)} pages, {label}): "
                f"word precision {precision:.1%}, recall {recall:.1%}"
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
        sample = chosen[len(chosen) // 2]
        print("  sample decoded:", decoded[sample][:200].replace("\n", " / "))
        print("  sample typed:  ", pages[sample][1][:200])


def ocr_pages(book: str) -> dict[int, str]:
    """archive.org's OCR of the PDF, by 1-based page, if downloaded into corpus/ocr."""
    manifest = [json.loads(line) for line in (CORPUS / "manifest.jsonl").open(encoding="utf-8")]
    url = next(b["url"] for b in manifest if str(b["book_id"]) == book)
    # archive.org names derived OCR files after the PDF, which may differ from the item.
    base = ROOT / "corpus" / "ocr" / Path(url).stem
    index_path = Path(f"{base}_hocr_pageindex.json.gz")
    text_path = Path(f"{base}_hocr_searchtext.txt.gz")
    if not index_path.exists() or not text_path.exists():
        return {}
    index = json.loads(gzip.decompress(index_path.read_bytes()))
    text = gzip.decompress(text_path.read_bytes()).decode("utf-8")
    return {i + 1: text[start:end] for i, (start, end, *_) in enumerate(index)}


if __name__ == "__main__":
    main()
