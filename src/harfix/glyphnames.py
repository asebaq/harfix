"""Arabic glyph names written out as text, and glyph codes written out as numbers.

When a font has no Unicode map, some extractors fall back on what the font does have.
docling-parse writes each glyph's name (`qafisolated yehmedial lamwithaleffinal`, glued
into one token per word) or, when the font has no names either, its code as a decimal
number (`179 75 154`). The names spell the letters exactly, so they can be turned back
into text; the codes cannot.

Glyph order follows the page from left to right, so a line of names is usually in visual
order. Each glyph is one unit: a ligature such as `lamwithalef` (لا) keeps its letters in
reading order when the line is reversed.
"""

from __future__ import annotations

import re
from functools import lru_cache

from .model import CharLM
from .normalize import letters_only

_LETTERS = {
    "hamza": "ء",
    "alefwithmaddaabove": "آ",
    "alefmaddaabove": "آ",
    "alefwithhamzaabove": "أ",
    "alefhamzaabove": "أ",
    "wawwithhamzaabove": "ؤ",
    "wawhamzaabove": "ؤ",
    "alefwithhamzabelow": "إ",
    "alefhamzabelow": "إ",
    "yehwithhamzaabove": "ئ",
    "yehhamzaabove": "ئ",
    "alef": "ا",
    "alefwasla": "ا",
    "beh": "ب",
    "tehmarbuta": "ة",
    "teh": "ت",
    "theh": "ث",
    "jeem": "ج",
    "hah": "ح",
    "khah": "خ",
    "dal": "د",
    "thal": "ذ",
    "reh": "ر",
    "zain": "ز",
    "seen": "س",
    "sheen": "ش",
    "sad": "ص",
    "dad": "ض",
    "tah": "ط",
    "zah": "ظ",
    "ain": "ع",
    "ghain": "غ",
    "feh": "ف",
    "qaf": "ق",
    "kaf": "ك",
    "lam": "ل",
    "meem": "م",
    "noon": "ن",
    "heh": "ه",
    "waw": "و",
    "alefmaksura": "ى",
    "yeh": "ي",
    "allah": "الله",
    "peh": "پ",
    "tcheh": "چ",
    "jeh": "ژ",
    "veh": "ڤ",
    "keheh": "ک",
    "gaf": "گ",
    "farsiyeh": "ی",
}
# Marks and elongation: dropped, since the extractor's glyph order does not say which letter
# a mark sits on, and search indexes strip them anyway.
_SILENT = {
    "fathatan",
    "dammatan",
    "kasratan",
    "fatha",
    "damma",
    "kasra",
    "shadda",
    "sukun",
    "superscriptalef",
    "tatweel",
}
_SIGNS = {
    "arabiccomma": "،",
    "arabicsemicolon": "؛",
    "arabicquestionmark": "؟",
    "arabicpercentsign": "٪",
    "ornateleftparenthesis": "﴾",
    "ornaterightparenthesis": "﴿",
    "righttoleftspace": " ",
    "hyphenminus": "-",
    "salla": "ﷺ",
}
for _i, _d in enumerate("zero one two three four five six seven eight nine".split()):
    _SIGNS["arabicindicdigit" + _d] = chr(0x0660 + _i)

_NAMES = {**_LETTERS, **dict.fromkeys(_SILENT, ""), **_SIGNS}
# Positional forms, low-mark variants and alternate-glyph suffixes that fonts append.
_SUFFIXES = ("isolated", "initial", "medial", "final", "isol", "init", "medi", "fina", "low")
_GLUE = "with"
_LONGEST = max(map(len, _NAMES))


def _names_at(token: str, start: int) -> list[tuple[int, str]]:
    """(end, letters) for every name that starts at `start`, with or without `arabic`."""
    out = []
    begins = {start, start + 6} if token.startswith("arabic", start) else {start}
    for begin in begins:
        for end in range(begin + 1, min(len(token), begin + _LONGEST) + 1):
            if token[begin:end] in _NAMES:
                out.append((end, _NAMES[token[begin:end]]))
    return out


@lru_cache(maxsize=4096)
def parse_token(token: str) -> tuple[str, ...] | None:
    """The glyphs of one token, each as its letters in reading order, or None when the
    token is not made only of Arabic glyph names. Ligatures (`lamwithalef`, `fehwithyeh`)
    are one glyph."""
    n = len(token)
    # best[i]: the fewest glyphs that spell token[:i].
    best: list[tuple[str, ...] | None] = [None] * (n + 1)
    best[0] = ()
    for i in range(n):
        if best[i] is None:
            continue
        # One glyph: a name, then `with` and another name any number of times, then
        # suffixes (`isolated`, `low`) and an alternate-glyph mark (`isolatedd`, `salla2`).
        stack = _names_at(token, i)
        while stack:
            end, letters = stack.pop()
            ends = [end]
            j = end
            while suffix := next((s for s in _SUFFIXES if token.startswith(s, j)), None):
                j += len(suffix)
                ends.append(j)
            if j < n and token[j] in "abcd0123456789":
                ends.append(j + 1)
            for e in ends:
                if best[e] is None or len(best[e]) > len(best[i]) + 1:
                    best[e] = (*best[i], letters)
                if token.startswith(_GLUE, e):
                    stack += [(e2, letters + more) for e2, more in _names_at(token, e + 4)]
    return best[n]


def _spelled(word: str) -> tuple[str, ...] | None:
    """The glyphs of a word that is written in glyph names. A single short name could be
    an English word (`seen`, `sad`); a form suffix or a second glyph makes it a name."""
    if not word or not ("a" <= word[0] <= "z"):
        return None
    glyphs = parse_token(word)
    if glyphs and (len(glyphs) > 1 or len(word) > 8):
        return glyphs
    return None


def glyph_name_words(text: str) -> int:
    """Words spelled in Arabic glyph names."""
    return sum(1 for word in text.split() if _spelled(word) is not None)


_NUMBER_WORD = re.compile(r"\d{1,5}")


def glyph_code_words(text: str) -> tuple[int, int]:
    """(bare integers that look like glyph codes, all words).

    Glyph codes repeat (every alef has the same code) but take many values, one per
    letter shape, mostly above the control range. Page numbers do not repeat, a table of
    years takes few values, and note markers are small; such numbers count as no codes.
    """
    words = text.split()
    numbers = [int(w) for w in words if _NUMBER_WORD.fullmatch(w)]
    kinds = len(set(numbers))
    if not 10 <= kinds <= 0.5 * len(numbers) or sorted(numbers)[len(numbers) // 2] < 20:
        return 0, len(words)
    return len(numbers), len(words)


def fix_allah(text: str) -> str:
    """Fonts draw الله either as one `allah` glyph or as `alef` and an `allah` glyph that
    holds only lam, lam, heh; the second spells االله, which is never a word."""
    return text.replace("االله", "الله")


def convert(text: str, model: CharLM) -> tuple[str, int]:
    """Spell out glyph-name words as Arabic; return the text and how many characters of
    glyph names were replaced.

    Each line is put in reading order: its glyphs are reversed when that reads better
    (the usual case, since names follow the page from left to right). Words that are not
    glyph names are kept as they are.
    """
    parsed = [[(word, _spelled(word)) for word in line.split(" ")] for line in text.split("\n")]

    def spell(pieces, backwards: bool) -> str:
        words = reversed(pieces) if backwards else pieces
        out = []
        for word, glyphs in words:
            if glyphs is None:
                out.append(word)
            else:
                word = "".join(_reverse_glyphs(glyphs) if backwards else glyphs)
                out.append(fix_allah(word))
        return " ".join(out)

    def bits(candidate: str) -> float:
        letters = letters_only(candidate)
        return model.bits_per_char(letters)[0] if letters else 0.0

    named = [p for p in parsed if any(g for _, g in p)]
    forward = "\n".join(spell(p, False) for p in named)
    backward = "\n".join(spell(p, True) for p in named)
    backwards = bits(backward) < bits(forward)
    changed = sum(len(word) for p in parsed for word, g in p if g is not None)
    out = [
        spell(p, backwards) if any(g for _, g in p) else " ".join(w for w, _ in p) for p in parsed
    ]
    return "\n".join(out), changed


def _reverse_glyphs(glyphs: tuple[str, ...]) -> list[str]:
    """Glyphs in reverse order, except runs of digits, which read left to right."""
    out: list[str] = []
    run: list[str] = []
    for glyph in reversed(glyphs):
        if glyph.isdigit():
            run.insert(0, glyph)
            continue
        out += run
        run = []
        out.append(glyph)
    return out + run
