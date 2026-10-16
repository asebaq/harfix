"""Character classes and the letter-only normalization used by the language model."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

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


def _is_presentation_form(ch: str) -> bool:
    cp = ord(ch)
    return 0xFB50 <= cp <= 0xFDFF or 0xFE70 <= cp <= 0xFEFF


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


def profile(text: str) -> CharProfile:
    """Count character classes in raw extracted text."""
    cid = len(_CID.findall(text))
    text = _CID.sub(" ", text)
    arabic = other = forms = pua = replacement = bidi = legacy = visible = 0
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
    return CharProfile(arabic, other, forms, pua, replacement, cid, bidi, legacy, visible)


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
