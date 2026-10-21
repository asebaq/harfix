"""Prototype: undo a font's wrong Unicode map as a substitution cipher, without typed text.

Usage:
    uv run python scripts/cipher_prototype.py

Some fonts carry a ToUnicode map that gives Arabic letters, but the wrong ones, and
always the same wrong one for a glyph. For each book and font, this looks for the letter
each extracted character stands for: the assignment under which the font's text reads best
under harfix's spaced letter model (hill climbing over single reassignments, from two
starts: the characters as they are, and a frequency match). Typed text is used only to
score the result.

Cases: the benchmark's font runs labelled broken that `scan` sends to OCR for
`same_script_substitution`. Controls: font runs labelled clean, which the solver must
leave as they are.

Results and the go/no-go decision: reports/cipher_prototype.md.
"""

from __future__ import annotations

import json
import math
import random
import re
import statistics
import unicodedata
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from pdfminer.high_level import extract_pages

from harfix import assess_text
from harfix.model import default_models
from harfix.normalize import (
    ARABIC_LETTERS,
    BOUNDARY,
    decompose_presentation_forms,
    letters_only,
)
from harfix.pdf import _collect_page

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "corpus" / "shamela_text"
SUB = re.compile(r"^[A-Z]{6}\+")
TARGETS = sorted(ARABIC_LETTERS)
MIN_LETTERS = 400  # less text than this cannot fix a substitution
MIN_GAIN = 1.0  # bits per occurrence a reassignment must gain


# ---------------------------------------------------------------- text


def _lines(text: str) -> list[list[list[str]]]:
    """Lines of words as lists of cipher symbols: every letter character, presentation
    forms decomposed first (a wrong map still gives one glyph one wrong letter), tatweel
    left out."""
    lines = []
    for raw_line in decompose_presentation_forms(text)[0].split("\n"):
        words = []
        for raw in raw_line.split():
            word = [ch for ch in raw if unicodedata.category(ch).startswith("L") and ch != "ـ"]
            if word:
                words.append(word)
        if words:
            lines.append(words)
    return lines


def _oriented(lines: list[list[list[str]]], lm) -> list[list[str]]:
    """Words, each line read in the direction its letters, as they show, score better
    in: extractors give right-to-left lines in visual or logical order, even mixed."""
    out = []
    for words in lines:
        shown = " ".join("".join(_start(s) for s in w) for w in words)
        forward = lm.bits_per_char(shown)[0]
        backward = lm.bits_per_char(shown[::-1])[0]
        out += [w[::-1] for w in reversed(words)] if backward < forward else words
    return out


def _start(symbol: str) -> str:
    """The letter a symbol shows as (regional forms folded), or alef for anything else."""
    return letters_only(symbol)[:1] or "ا"


# ---------------------------------------------------------------- solver


class Solver:
    """Score of an assignment symbol -> letter: the letter model's log probability of the
    words it spells, from counts of the symbols' 4-grams (boundaries included)."""

    def __init__(self, words: list[list[str]], lm) -> None:
        self.lm = lm
        self.order = lm.order
        pad = [BOUNDARY] * (self.order - 1)
        grams: Counter = Counter()
        for word in words:
            seq = pad + word + [BOUNDARY]
            for i in range(self.order - 1, len(seq)):
                grams[tuple(seq[i - self.order + 1 : i + 1])] += 1
        self.grams = grams
        self.by_symbol: dict[str, list[tuple]] = defaultdict(list)
        for gram in grams:
            for s in set(gram):
                if s != BOUNDARY:
                    self.by_symbol[s].append(gram)
        self.symbols = sorted(
            self.by_symbol, key=lambda s: -sum(grams[g] for g in self.by_symbol[s])
        )
        self._cache: dict[tuple[str, str], float] = {}
        self.occurrences = Counter(s for word in words for s in word)

    def _logp(self, history: str, char: str) -> float:
        key = (history, char)
        if key not in self._cache:
            self._cache[key] = math.log(self.lm.prob(char, history))
        return self._cache[key]

    def _gram_score(self, gram: tuple, f: dict[str, str]) -> float:
        mapped = [s if s == BOUNDARY else f[s] for s in gram]
        return self.grams[gram] * self._logp("".join(mapped[:-1]), mapped[-1])

    def score(self, f: dict[str, str]) -> float:
        return sum(self._gram_score(g, f) for g in self.grams)

    def climb(self, f: dict[str, str], rounds: int = 6) -> tuple[dict[str, str], float]:
        """Reassign one symbol at a time while that gains at least MIN_GAIN bits per
        occurrence: a wrong map costs several bits wherever the symbol occurs, while
        reassigning a right letter gains a little only where the model is unsure."""
        f = dict(f)
        for _ in range(rounds):
            changed = False
            for s in self.symbols:
                grams = self.by_symbol[s]
                need = MIN_GAIN * math.log(2) * self.occurrences[s]
                current = f[s]
                base = sum(self._gram_score(g, f) for g in grams)
                best, best_gain = current, need
                for letter in TARGETS:
                    if letter == current:
                        continue
                    f[s] = letter
                    gain = sum(self._gram_score(g, f) for g in grams) - base
                    if gain > best_gain:
                        best, best_gain = letter, gain
                f[s] = best
                changed |= best != current
            if not changed:
                break
        return f, self.score(f)

    def solve(self, seed: int = 0) -> tuple[dict[str, str], float]:
        identity = {s: _start(s) for s in self.symbols}
        # Frequency match: the most frequent symbols to the most frequent letters.
        counts = Counter({s: sum(self.grams[g] for g in self.by_symbol[s]) for s in self.symbols})
        letter_freq = sorted(TARGETS, key=lambda c: -self.lm.prob(c, ""))
        frequency = {
            s: letter_freq[min(i, len(letter_freq) - 1)]
            for i, (s, _) in enumerate(counts.most_common())
        }
        rng = random.Random(seed)
        results = [self.climb(identity), self.climb(frequency)]
        best = max(results, key=lambda r: r[1])
        for _ in range(3):  # perturb the best and climb again
            f = dict(best[0])
            for s in rng.sample(self.symbols, k=max(1, len(self.symbols) // 5)):
                f[s] = rng.choice(TARGETS)
            results.append(self.climb(f))
            best = max(results, key=lambda r: r[1])
        return best


# ---------------------------------------------------------------- cases


def _runs(job) -> dict[str, str]:
    """Each font's text on the given pages of one PDF."""
    path, pages = job
    runs: dict[str, list[str]] = defaultdict(list)
    for layout in extract_pages(str(path), page_numbers=[p - 1 for p in pages]):
        for font, text in _collect_page(layout)[0].items():
            runs[font].append(text)
    return {font: "\n".join(texts) for font, texts in runs.items()}


def _cases():
    results = json.loads((CORPUS / "benchmark_runs.json").read_text(encoding="utf-8"))
    files = {}
    for line in (CORPUS / "manifest.jsonl").open(encoding="utf-8"):
        b = json.loads(line)
        files["+".join(str(i) for i in b["pdf_books"])] = CORPUS / b["file"]
    cases = defaultdict(lambda: {"pages": set(), "kind": None})
    for r in results:
        for p in r["pages"]:
            for f in p["fonts"]:
                if f["label"] == "broken" and "same_script_substitution" in f["reasons"]:
                    kind = "broken"
                elif f["label"] == "clean" and f["route"] == "keep" and f["words"] >= 40:
                    kind = "clean"
                else:
                    continue
                case = cases[(r["book_id"], f["font"])]
                case["pages"].add(p["page"])
                case["kind"] = case["kind"] or kind
    return files, cases


def run_case(job):
    book, font, kind, path, pages = job
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    text = _runs((path, sorted(pages))).get(font, "")
    lm = default_models().spaced
    words = _oriented(_lines(text), lm)
    letters = sum(len(w) for w in words)
    arabic = sum(1 for w in words for ch in w if 0x0600 <= ord(ch) <= 0x06FF or ord(ch) >= 0xFB50)
    if letters < MIN_LETTERS or arabic < 0.5 * letters:
        return None
    solver = Solver(words, lm)
    identity = {s: _start(s) for s in solver.symbols}
    f, score = solver.solve()
    changed = {s: t for s, t in f.items() if t != identity[s]}
    decoded = "".join(f.get(ch, ch) for ch in decompose_presentation_forms(text)[0])
    return {
        "book": book,
        "font": SUB.sub("", font),
        "kind": kind,
        "letters": letters,
        "symbols": len(solver.symbols),
        "changed": len(changed),
        "gain_bits": (score - solver.score(identity)) / letters / math.log(2),
        "before": text,
        "after": decoded,
        "route_after": assess_text(decoded, order_known=False).route,
    }


def main() -> None:
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    import benchmark

    files, cases = _cases()
    rng = random.Random(0)
    broken = [(k, v) for k, v in cases.items() if v["kind"] == "broken"]
    clean = [(k, v) for k, v in cases.items() if v["kind"] == "clean"]
    clean = rng.sample(clean, min(len(clean), 40))
    jobs = [(b, font, v["kind"], files[b], v["pages"]) for (b, font), v in broken + clean]
    with ProcessPoolExecutor() as pool:
        results = [r for r in pool.map(run_case, jobs) if r]

    texts = sorted((CORPUS / "text").glob("*.jsonl"))
    typed = "\n".join(json.loads(line)["text"] for p in texts for line in p.open(encoding="utf-8"))
    vocab = benchmark.vocabulary(typed, None)
    rows = []
    for r in results:
        before = benchmark.label_run(r["before"], vocab)
        after = benchmark.label_run(r["after"], vocab)
        rows.append({**r, "share_before": before[2], "share_after": after[2]})
        print(
            f"{r['kind']:6} {r['book']:>6} {r['font'][:24]:24} letters {r['letters']:6} "
            f"symbols {r['symbols']:3} changed {r['changed']:3} gain {r['gain_bits']:5.2f} bits "
            f"found {before[2]:.0%} -> {after[2]:.0%} route {r['route_after']}"
        )
    for kind in ("broken", "clean"):
        chosen = [r for r in rows if r["kind"] == kind]
        if chosen:
            print(
                f"{kind}: {len(chosen)} font runs, median found "
                f"{statistics.median(r['share_before'] for r in chosen):.0%} -> "
                f"{statistics.median(r['share_after'] for r in chosen):.0%}, "
                f"worse {sum(r['share_after'] < r['share_before'] - 0.02 for r in chosen)}"
            )
    (ROOT / "build").mkdir(exist_ok=True)
    (ROOT / "build" / "cipher_rows.json").write_text(
        json.dumps(
            [{k: v for k, v in r.items() if k not in ("before", "after")} for r in rows], indent=1
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
