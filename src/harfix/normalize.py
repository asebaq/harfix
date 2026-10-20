"""Character classes and the letter-only normalization used by the language model."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from itertools import pairwise

# Base Arabic letters the model distinguishes. Hamza carriers stay distinct because
# wrong-ToUnicode fonts frequently confuse them.
ARABIC_LETTERS = frozenset(chr(cp) for cp in [*range(0x0621, 0x063B), *range(0x0641, 0x064B)])
BOUNDARY = " "
ALPHABET = "".join(sorted(ARABIC_LETTERS)) + BOUNDARY

# Regional letters folded onto their closest base letter so Persian-style keyboards and
# fonts do not look like corruption.
_FOLD = {
    "\u0671": "\u0627",  # alef wasla -> alef
    "\u06cc": "\u064a",  # farsi yeh -> yeh
    "\u06a9": "\u0643",  # keheh -> kaf
    "\u06c1": "\u0647",  # heh goal -> heh
    "\u06d5": "\u0647",  # ae -> heh
    "\u067e": "\u0628",  # peh -> beh
    "\u0686": "\u062c",  # tcheh -> jeem
    "\u06a4": "\u0641",  # veh -> feh
    "\u06af": "\u0643",  # gaf -> kaf
}
_DROP = frozenset(
    [chr(cp) for cp in range(0x064B, 0x0660)]  # harakat, tanween, shadda, sukun
    + ["\u0670", "\u0640"]  # dagger alef, tatweel
)
_BIDI_CONTROLS = frozenset(
    [
        "\u200e",
        "\u200f",
        "\u061c",
        *map(chr, range(0x202A, 0x202F)),
        *map(chr, range(0x2066, 0x206A)),
    ]
)


# Arabic presentation forms: shaped letters and ligatures that NFKC decomposes into base
# letters. Symbols in the same blocks with no decomposition, such as the ornate
# parentheses ﴾﴿ that wrap Quran quotations, are punctuation and are left out.
_FORMS = frozenset(
    chr(cp)
    for cp in [*range(0xFB50, 0xFE00), *range(0xFE70, 0xFF00)]
    if unicodedata.normalize("NFKC", chr(cp)) != chr(cp)
)
# Presentation Forms-A: ligatures that ordinary shaping output almost never uses.
_LIGATURES = frozenset(ch for ch in _FORMS if ord(ch) < 0xFE00)
_LIGATURE_FORMS = re.compile("[" + re.escape("".join(sorted(_LIGATURES))) + "]")


def _is_presentation_form(ch: str) -> bool:
    return ch in _FORMS


def _is_ligature_form(ch: str) -> bool:
    return ch in _LIGATURES


def drop_ligature_forms(text: str) -> str:
    """Replace Presentation Forms-A ligatures with spaces (used for Quran glyph fonts)."""
    return _LIGATURE_FORMS.sub(" ", text)


def _is_private_use(ch: str) -> bool:
    cp = ord(ch)
    if 0xF000 <= cp <= 0xF0FF:
        return False  # Microsoft Symbol/Wingdings glyphs (bullets, arrows), not text.
    return 0xE000 <= cp <= 0xF8FF or 0xF0000 <= cp <= 0x10FFFD


def _is_arabic_block(ch: str) -> bool:
    cp = ord(ch)
    return (
        0x0600 <= cp <= 0x06FF
        or 0x0750 <= cp <= 0x077F
        or 0x08A0 <= cp <= 0x08FF
        or 0xFB50 <= cp <= 0xFDFF
        or 0xFE70 <= cp <= 0xFEFF
    )


# pdfminer writes "(cid:N)" for glyph codes it cannot map to Unicode at all.
_CID = re.compile(r"\(cid:\d+\)")
_PRESENTATION_RUN = re.compile("[" + re.escape("".join(sorted(_FORMS))) + "]+")
_LATIN_WORD = re.compile(r"[A-Za-z]+")
# Punctuation that may close or open a real word; anything else inside a word is suspect.
_WORD_EDGES = ".,;:!?()[]{}\"'«»-–—/"
_INNER_SYMBOL = re.compile(r"[0-9!\"#$%&()*+,/:;<=>?@\[\\\]^_`{|}~]")
_CASE_FLIP = re.compile(r"[a-z][A-Z]")
# Non-ASCII punctuation that is normal in Arabic typesetting.
_ARABIC_TYPOGRAPHY = frozenset("«»–—…•‘’“”\u00a0")


def _is_legacy_symbol(ch: str) -> bool:
    """Latin-1/Latin Extended letters and general symbols, where pre-Unicode Arabic lands."""
    cp = ord(ch)
    if ch in _ARABIC_TYPOGRAPHY:
        return False
    return 0x0080 <= cp <= 0x024F or 0x2000 <= cp <= 0x2BFF


@dataclass(frozen=True)
class CharProfile:
    """Raw character counts, measured before any normalization."""

    arabic_letters: int
    other_letters: int
    presentation_forms: int
    private_use: int
    replacement: int
    cid_codes: int
    bidi_controls: int
    legacy_symbols: int
    visible: int
    # Quran glyph fonts (King Fahd Complex "QCF") store one glyph per word under
    # Presentation Forms-A code points numbered in reading order, so the text is glyph
    # IDs, not shaped letters.
    ligature_forms: int
    presentation_runs: int
    short_presentation_runs: int
    consecutive_ligature_pairs: int
    # ASCII letters outside all-capitals words; pre-Unicode Arabic fonts often land here.
    latin_letters: int
    latin_vowels: int
    # Whitespace-separated words with ASCII letters, and those mixing in digits, symbols
    # or a lower-to-upper case flip (`h&c%G`, `pEqLGQb`): rare in real Latin text.
    latin_words: int
    irregular_latin_words: int
    # Words with no letters that are not numbers (`0)#`, `-!/!1-!/`): pre-Unicode fonts
    # mapped onto ASCII digits and punctuation. `plain_words` excludes plain numbers.
    symbol_words: int
    plain_words: int
    # U+FFFD with Arabic letters on both sides: often an unmapped elongation (kashida)
    # glyph inside an otherwise intact word.
    inner_replacement: int
    # All whitespace-separated words, and those that are one ASCII character other than a
    # digit or leader punctuation (`. . .`), counted only when at least ten different
    # characters occur so: what a pre-Unicode font looks like when an extractor splits text
    # at every font change and the font spreads each word over several subsets. A bracket
    # or bullet font repeats a few characters.
    words: int = 0
    fragment_words: int = 0

    @property
    def arabic_ratio(self) -> float:
        letters = self.arabic_letters + self.other_letters
        return self.arabic_letters / letters if letters else 0.0

    @property
    def presentation_form_ratio(self) -> float:
        return self.presentation_forms / self.arabic_letters if self.arabic_letters else 0.0

    @property
    def unmapped(self) -> int:
        """Glyphs with no real Unicode mapping: private-use, U+FFFD, or raw CID codes."""
        return self.private_use + self.replacement + self.cid_codes

    @property
    def unmapped_ratio(self) -> float:
        glyphs = self.arabic_letters + self.other_letters + self.unmapped
        return self.unmapped / glyphs if glyphs else 0.0

    @property
    def legacy_ratio(self) -> float:
        """Share of visible characters that are non-ASCII, non-Arabic symbols.

        Fonts using pre-Unicode Arabic encodings extract as Latin-1 and math symbols
        (for example `Âd‡;« ≤∞`) instead of Arabic letters.
        """
        return self.legacy_symbols / self.visible if self.visible else 0.0

    @property
    def ligature_form_share(self) -> float:
        return self.ligature_forms / self.presentation_forms if self.presentation_forms else 0.0

    @property
    def short_presentation_run_share(self) -> float:
        """Share of presentation-form runs that are one or two glyphs long."""
        runs = self.presentation_runs
        return self.short_presentation_runs / runs if runs else 0.0

    @property
    def consecutive_ligature_share(self) -> float:
        """Share of successive Presentation Forms-A characters whose code points differ by 1."""
        pairs = self.ligature_forms - 1
        return self.consecutive_ligature_pairs / pairs if pairs > 0 else 0.0

    @property
    def latin_vowel_ratio(self) -> float:
        """Vowels among ASCII letters: about 0.4 in Latin-script languages."""
        return self.latin_vowels / self.latin_letters if self.latin_letters else 0.0

    @property
    def irregular_latin_word_ratio(self) -> float:
        return self.irregular_latin_words / self.latin_words if self.latin_words else 0.0

    @property
    def symbol_word_ratio(self) -> float:
        return self.symbol_words / self.plain_words if self.plain_words else 0.0


_NUMBER = re.compile(r"[+\-−±$€£]?\d[\d.,/:\-–]*[%$€£]?")
_ASCII_SYMBOL = re.compile(r"[!-/:-@\[-`{-~]")
_INNER_REPLACEMENT = re.compile(r"(?<=[\u0621-\u0652])\ufffd+(?=[\u0621-\u0652])")
_LEADERS = frozenset(".-_*=~")


def _symbol_words(text: str) -> tuple[int, int]:
    """(words other than plain numbers, those made of digits and ASCII symbols only)."""
    plain = symbols = 0
    for raw in text.split():
        word = raw.strip(_WORD_EDGES)
        if not word or _NUMBER.fullmatch(word):
            continue
        plain += 1
        if len(word) >= 2 and _ASCII_SYMBOL.search(word) and not any(c.isalpha() for c in word):
            symbols += 1
    return plain, symbols


def drop_inner_replacement(text: str) -> tuple[str, int]:
    """Delete U+FFFD that sits between Arabic letters; return the text and how many."""
    count = 0

    def drop(match: re.Match) -> str:
        nonlocal count
        count += len(match.group())
        return ""

    return _INNER_REPLACEMENT.sub(drop, text), count


def decompose_presentation_forms(text: str) -> tuple[str, int]:
    """NFKC only on Arabic presentation forms; return the text and how many were changed."""
    count = 0
    out = []
    for ch in text:
        if ch in _FORMS:
            count += 1
            # A few isolated-diacritic forms decompose with a leading space; drop it.
            out.append(unicodedata.normalize("NFKC", ch).lstrip(" "))
        else:
            out.append(ch)
    return "".join(out), count


_BIDI_RUN = re.compile("[" + re.escape("".join(sorted(_BIDI_CONTROLS))) + "]+")


def drop_bidi_controls(text: str) -> tuple[str, int]:
    """Delete Unicode bidi formatting characters; return the text and how many.

    Extractors such as pdftotext wrap script changes in embedding marks. Where a run of
    them sat between two visible characters (`كلمةhindawi`), a space keeps the words apart.
    """
    count = 0

    def drop(match: re.Match) -> str:
        nonlocal count
        count += len(match.group())
        start, end = match.start(), match.end()
        between = 0 < start and end < len(text)
        if between and not text[start - 1].isspace() and not text[end].isspace():
            return " "
        return ""

    return _BIDI_RUN.sub(drop, text), count


def _latin_words(text: str) -> tuple[int, int]:
    words = irregular = 0
    for raw in text.split():
        word = raw.strip(_WORD_EDGES)
        if len(word) < 2 or not _LATIN_WORD.search(word):
            continue
        words += 1
        irregular += bool(_INNER_SYMBOL.search(word) or _CASE_FLIP.search(word))
    return words, irregular


def profile(text: str) -> CharProfile:
    """Count character classes in raw extracted text."""
    cid = len(_CID.findall(text))
    text = _CID.sub(" ", text)
    runs = [len(run) for run in _PRESENTATION_RUN.findall(text)]
    codes = [ord(ch) for ch in _LIGATURE_FORMS.findall(text)]
    consecutive = sum(1 for a, b in pairwise(codes) if abs(b - a) == 1)
    latin = vowels = 0
    for word in _LATIN_WORD.findall(text):
        if len(word) > 1 and word.isupper():
            continue  # acronyms and Roman numerals carry no vowel signal
        latin += len(word)
        vowels += sum(1 for c in word.lower() if c in "aeiouy")
    latin_words, irregular_words = _latin_words(text)
    plain_words, symbol_words = _symbol_words(text)
    inner_replacement = sum(len(m) for m in _INNER_REPLACEMENT.findall(text))
    tokens = text.split()
    singles = [w for w in tokens if len(w) == 1 and w.isascii() and not w.isdigit()]
    singles = [w for w in singles if w not in _LEADERS]
    fragments = len(singles) if len(set(singles)) >= 10 else 0
    arabic = other = forms = ligatures = pua = replacement = bidi = legacy = visible = 0
    for ch in text:
        if ch.isspace():
            continue
        visible += 1
        if ch == "\ufffd":
            replacement += 1
        elif _is_private_use(ch):
            pua += 1
        elif ch in _BIDI_CONTROLS:
            bidi += 1
        elif _is_presentation_form(ch):
            forms += 1
            ligatures += _is_ligature_form(ch)
            # A presentation-form glyph is still an Arabic letter once decomposed.
            arabic += sum(1 for c in unicodedata.normalize("NFKC", ch) if c in ARABIC_LETTERS)
        elif ch in ARABIC_LETTERS or ch in _FOLD:
            arabic += 1
        elif ch.isalpha() and ch.isascii():
            other += 1
        elif _is_legacy_symbol(ch):
            if ch.isalpha():
                other += 1
            legacy += 1
        elif ch.isalpha():
            other += 1  # Greek, Cyrillic, and other real scripts.
    return CharProfile(
        arabic,
        other,
        forms,
        pua,
        replacement,
        cid,
        bidi,
        legacy,
        visible,
        ligature_forms=ligatures,
        presentation_runs=len(runs),
        short_presentation_runs=sum(1 for n in runs if n <= 2),
        consecutive_ligature_pairs=consecutive,
        latin_letters=latin,
        latin_vowels=vowels,
        latin_words=latin_words,
        irregular_latin_words=irregular_words,
        symbol_words=symbol_words,
        plain_words=plain_words,
        inner_replacement=inner_replacement,
        words=len(tokens),
        fragment_words=fragments,
    )


def letters_only(text: str) -> str:
    """Reduce text to base Arabic letters separated by single spaces.

    Presentation forms are decomposed, diacritics and tatweel removed, regional letters
    folded, and every other character becomes a word boundary.
    """
    out: list[str] = []
    for ch in unicodedata.normalize("NFKC", text):
        if ch in _DROP:
            continue
        ch = _FOLD.get(ch, ch)
        if ch in ARABIC_LETTERS:
            out.append(ch)
        elif out and out[-1] != BOUNDARY:
            out.append(BOUNDARY)
    return "".join(out).strip()


# Rules and leaders drawn with an elongated letter glyph (often dal or tatweel-like
# shapes) extract as long runs of one letter. Real words never repeat a letter six times.
_DECORATION = re.compile(r"([^ ])\1{5,}")


def strip_decorations(letters: str) -> tuple[str, int]:
    """Replace runs of six or more identical letters with a boundary; return the count."""
    cleaned, runs = _DECORATION.subn(BOUNDARY, letters)
    if runs:
        cleaned = " ".join(cleaned.split())
    return cleaned, runs
