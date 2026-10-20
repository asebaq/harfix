"""Turn character statistics and model scores into a keep / repair / reextract / ocr verdict."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from importlib import resources

from .glyphnames import convert as convert_glyph_names
from .glyphnames import glyph_code_words, glyph_name_words
from .model import CharLM, ModelPair, default_models
from .normalize import BOUNDARY, drop_ligature_forms, letters_only, profile, strip_decorations

# Ordered from least to most severe; a page takes the most severe route of its parts.
ROUTES = ("keep", "repair", "reextract", "ocr")
_MIN_LINE_LETTERS = 20
# `assess_document` splits text without page breaks into pieces of about this many letters.
SEGMENT_LETTERS = 500


@dataclass(frozen=True)
class Thresholds:
    """Decision thresholds. Packaged values come from `scripts/calibrate.py`."""

    min_letters: int = 80
    # Mean surprisal (bits/character) of the reading-order-corrected text.
    substitution_bits: float = 4.7
    # A character at least this surprising is a spike; too many spikes means swapped letters.
    spike_bits: float = 18.0
    spike_rate: float = 0.02
    # Spike rates on short runs (headings, captions) are too noisy to act on.
    spike_min_letters: int = 200
    # Implausible text whose letters are fine once spaces are removed has broken word spacing.
    unspaced_bits: float = 5.4
    short_token_ratio: float = 0.46
    orientation_margin: float = 0.5
    presentation_form_ratio: float = 0.05
    unmapped_ratio: float = 0.02
    unmapped_min_glyphs: int = 5
    # Pre-Unicode Arabic fonts: mostly Latin-1/math symbols and almost no Arabic letters.
    legacy_ratio: float = 0.15
    legacy_min_visible: int = 30
    # Pre-Unicode Arabic fonts mapped onto ASCII: Latin "words" with almost no vowels, or
    # with digits, symbols and case flips inside them.
    latin_min_words: int = 15
    latin_vowel_ratio: float = 0.25
    latin_irregular_ratio: float = 0.3
    # Pre-Unicode Arabic fonts mapped onto ASCII digits and punctuation only.
    symbol_min_words: int = 8
    symbol_word_ratio: float = 0.4
    # Quran glyph fonts: one Presentation Forms-A code point per word, numbered in order.
    quran_min_forms: int = 8
    quran_ligature_share: float = 0.5
    quran_short_run_share: float = 0.6
    quran_consecutive_share: float = 0.5
    transposition_ratio: float = 0.27
    mixed_order_min_share: float = 0.2
    # Bidi formatting characters (embedding marks): invisible, but they stick to words.
    bidi_min_controls: int = 3
    # Fonts without a Unicode map, as some extractors (docling-parse) write them: each
    # glyph's name (`qafisolated`), which spells the letter, or its code as a number.
    glyph_name_min_words: int = 8
    glyph_code_min_words: int = 20
    glyph_code_share: float = 0.6
    # Pre-Unicode fonts split one word over several fonts; extractors that break text at
    # font changes (docling-parse) then write one ASCII character per word.
    fragment_min_words: int = 40
    fragment_share: float = 0.6

    @classmethod
    def from_dict(cls, data: dict) -> Thresholds:
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**known)


@lru_cache(maxsize=1)
def default_thresholds() -> Thresholds:
    path = resources.files("harfix") / "data" / "thresholds.json"
    if not path.is_file():
        return Thresholds()
    return Thresholds.from_dict(json.loads(path.read_text(encoding="utf-8"))["thresholds"])


@dataclass(frozen=True)
class Measurements:
    letters: int
    orientation: str  # "logical", "visual" or "unknown"
    visual_line_share: float
    bits: float
    spike_rate: float
    bits_unspaced: float
    short_token_ratio: float
    transposition_ratio: float
    decoration_runs: int


def line_direction(letters: str, model: CharLM, margin: float) -> bool | None:
    """True if a line of base letters reads better backwards (visual order), False if
    forwards, None if it is too short or too close to call."""
    if len(letters.replace(BOUNDARY, "")) < _MIN_LINE_LETTERS:
        return None
    forward, _ = model.bits_per_char(letters)
    backward, _ = model.bits_per_char(letters[::-1])
    if forward - backward > margin:
        return True
    if backward - forward > margin:
        return False
    return None


def measure(text: str, models: ModelPair, thresholds: Thresholds) -> Measurements:
    """Model-based measurements of `text` after correcting each line's reading direction."""
    model = models.spaced
    margin = thresholds.orientation_margin
    lines, decoration_runs = [], 0
    for raw in text.splitlines():
        line, runs = strip_decorations(letters_only(raw))
        decoration_runs += runs
        if line:
            lines.append(line)
    decisions = [line_direction(line, model, margin) for line in lines]  # True = visual
    visual_letters = sum(
        len(line.replace(BOUNDARY, "")) for line, d in zip(lines, decisions, strict=True) if d
    )
    logical_letters = sum(
        len(line.replace(BOUNDARY, ""))
        for line, d in zip(lines, decisions, strict=True)
        if d is False
    )
    if visual_letters or logical_letters:
        document_visual = visual_letters > logical_letters
        orientation = "visual" if document_visual else "logical"
    else:
        joined = BOUNDARY.join(lines)
        forward, _ = model.bits_per_char(joined)
        backward, _ = model.bits_per_char(joined[::-1])
        document_visual = forward - backward > margin
        if document_visual:
            orientation = "visual"
        else:
            orientation = "logical" if backward - forward > margin else "unknown"
    decided = visual_letters + logical_letters

    oriented = BOUNDARY.join(
        line[::-1] if (document_visual if visual is None else visual) else line
        for line, visual in zip(lines, decisions, strict=True)
    )
    surprisals = model.surprisals(oriented)
    unspaced = oriented.replace(BOUNDARY, "")
    bits_unspaced, _ = models.unspaced.bits_per_char(unspaced)

    words = oriented.split(BOUNDARY) if oriented else []
    al_words = sum(1 for w in words if len(w) >= 3 and w.startswith("ال"))
    swapped = sum(1 for w in words if len(w) >= 4 and w[0] == "ا" and w[2] == "ل" and w[1] != "ل")

    return Measurements(
        letters=len(unspaced),
        orientation=orientation,
        visual_line_share=visual_letters / decided if decided else 0.0,
        bits=sum(surprisals) / len(surprisals) if surprisals else 0.0,
        spike_rate=(
            sum(1 for s in surprisals if s >= thresholds.spike_bits) / len(surprisals)
            if surprisals
            else 0.0
        ),
        bits_unspaced=bits_unspaced,
        short_token_ratio=sum(1 for w in words if len(w) <= 2) / len(words) if words else 0.0,
        transposition_ratio=swapped / (al_words + swapped) if al_words + swapped else 0.0,
        decoration_runs=decoration_runs,
    )


@dataclass
class Assessment:
    route: str
    reasons: list[str]
    sufficient: bool
    metrics: dict[str, float | int | str] = field(default_factory=dict)

    @property
    def decisive(self) -> bool:
        """Judged on enough text, or flagged by a check that needs no minimum length."""
        return self.sufficient or self.route != "keep"

    def to_dict(self) -> dict:
        return asdict(self)


def assess_text(
    text: str,
    *,
    order_known: bool = True,
    models: ModelPair | None = None,
    thresholds: Thresholds | None = None,
) -> Assessment:
    """Assess one piece of extracted Arabic text.

    `order_known=True` is for an extractor's final output, where reading order is part of
    what is being checked. `order_known=False` is for raw PDF text-layer runs whose order
    depends on the extractor; reading-order faults are not reported then, and numbers are
    taken as real digits, since a raw run writes an unmapped glyph as `(cid:N)`, never as
    its code.
    """
    models = models or default_models()
    t = thresholds or default_thresholds()
    reasons: list[str] = []
    route = "keep"

    def flag(reason: str, new_route: str) -> None:
        nonlocal route
        reasons.append(reason)
        if ROUTES.index(new_route) > ROUTES.index(route):
            route = new_route

    names = glyph_name_words(text)
    if names >= t.glyph_name_min_words:
        # The names spell the letters: judge the text they spell.
        flag("glyph_names", "repair")
        text, _ = convert_glyph_names(text, models.spaced)
    codes, words = glyph_code_words(text)
    prof = profile(text)
    if (
        order_known
        and codes >= t.glyph_code_min_words
        and codes > t.glyph_code_share * words
        and codes > prof.arabic_letters
    ):
        flag("unmapped_glyphs", "ocr")
    metrics: dict[str, float | int | str] = {
        "arabic_letters": prof.arabic_letters,
        "arabic_ratio": round(prof.arabic_ratio, 4),
        "presentation_form_ratio": round(prof.presentation_form_ratio, 4),
        "unmapped_ratio": round(prof.unmapped_ratio, 4),
        "legacy_ratio": round(prof.legacy_ratio, 4),
        "latin_vowel_ratio": round(prof.latin_vowel_ratio, 4),
        "irregular_latin_word_ratio": round(prof.irregular_latin_word_ratio, 4),
        "bidi_controls": prof.bidi_controls,
        "glyph_name_words": names,
        "glyph_code_words": codes,
    }

    # These are visible even when too few Arabic letters survive to score.
    elongation = False
    if prof.unmapped >= t.unmapped_min_glyphs and prof.unmapped_ratio > t.unmapped_ratio:
        if prof.unmapped == prof.replacement == prof.inner_replacement:
            # Every unmapped glyph sits inside a word: judge the words without them below.
            elongation = True
            text = text.replace("\ufffd", "")
        else:
            flag("unmapped_glyphs", "ocr")
    symbol_legacy = prof.visible >= t.legacy_min_visible and prof.legacy_ratio > t.legacy_ratio
    ascii_legacy = prof.latin_words >= t.latin_min_words and (
        prof.latin_vowel_ratio < t.latin_vowel_ratio
        or prof.irregular_latin_word_ratio > t.latin_irregular_ratio
    )
    digit_legacy = (
        prof.symbol_words >= t.symbol_min_words and prof.symbol_word_ratio > t.symbol_word_ratio
    )
    # Latin text split into letters (a page of formulas) still has words between them.
    fragment_legacy = (
        prof.fragment_words >= t.fragment_min_words
        and prof.fragment_words > t.fragment_share * prof.words
        and prof.fragment_words > 4 * prof.latin_words
    )
    legacy = symbol_legacy or ascii_legacy or digit_legacy or fragment_legacy
    if prof.arabic_ratio < 0.2 and legacy:
        flag("legacy_encoding", "ocr")
    if prof.bidi_controls >= t.bidi_min_controls:
        flag("bidi_controls", "repair")
    if (
        prof.presentation_forms >= t.quran_min_forms
        and prof.ligature_form_share > t.quran_ligature_share
        and prof.short_presentation_run_share > t.quran_short_run_share
        and prof.consecutive_ligature_share > t.quran_consecutive_share
    ):
        # Glyph IDs, not letters: NFKC would turn them into wrong words. Judge the rest.
        flag("quran_glyph_codes", "ocr")
        text = drop_ligature_forms(text)
        prof = profile(text)

    m = measure(text, models, t)
    metrics["arabic_letters"] = m.letters
    spiky = m.letters >= t.spike_min_letters and m.spike_rate > t.spike_rate
    implausible = m.letters >= t.min_letters and (m.bits > t.substitution_bits or spiky)
    if elongation:
        if m.letters >= t.min_letters and not implausible:
            # The words read correctly once the unmapped glyphs are gone: they were
            # elongation (kashida) glyphs, and deleting them is a safe repair.
            flag("unmapped_elongation", "repair")
        else:
            flag("unmapped_glyphs", "ocr")
    if m.letters < t.min_letters:
        if not reasons:
            reasons.append("insufficient_arabic_text")
        return Assessment(route, reasons, False, metrics)

    metrics.update(
        orientation=m.orientation,
        bits=round(m.bits, 4),
        spike_rate=round(m.spike_rate, 4),
        bits_unspaced=round(m.bits_unspaced, 4),
        short_token_ratio=round(m.short_token_ratio, 4),
        decoration_runs=m.decoration_runs,
    )
    # Only meaningful for an extractor's final output. In a raw text-layer scan the spacing
    # comes from harfix's own extraction, so implausible text is treated as wrong letters.
    spacing_only = (
        order_known
        and m.short_token_ratio > t.short_token_ratio
        and m.bits_unspaced <= t.unspaced_bits
    )
    if spacing_only:
        # The letters are right; the extractor split words apart.
        flag("lost_word_boundaries", "reextract")
    elif implausible:
        # Even after fixing the reading direction the letters do not form Arabic words:
        # the font's glyph-to-letter mapping is wrong.
        flag("same_script_substitution", "ocr")
    if prof.presentation_form_ratio > t.presentation_form_ratio:
        flag("presentation_forms", "repair")

    if order_known and not implausible:
        metrics.update(
            visual_line_share=round(m.visual_line_share, 4),
            transposition_ratio=round(m.transposition_ratio, 4),
        )
        if t.mixed_order_min_share <= m.visual_line_share <= 1 - t.mixed_order_min_share:
            flag("mixed_reading_order", "reextract")
        elif m.orientation == "visual":
            flag("visual_order", "repair")
        if m.transposition_ratio > t.transposition_ratio:
            flag("lam_alef_transposition", "reextract")

    return Assessment(route, reasons, True, metrics)


@dataclass
class Segment:
    """One page (text split at form feeds) or one run of lines of an extractor's output."""

    index: int
    page: int | None
    start_line: int
    end_line: int
    assessment: Assessment

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "page": self.page,
            "start_line": self.start_line,
            "end_line": self.end_line,
            **self.assessment.to_dict(),
        }


@dataclass
class TextReport:
    route: str
    reasons: list[str]
    segments: list[Segment]

    def to_dict(self) -> dict:
        return {
            "route": self.route,
            "reasons": self.reasons,
            "segments": [s.to_dict() for s in self.segments],
        }


def worst(assessments: list[Assessment]) -> tuple[str, list[str]]:
    """Most severe route, with the reasons behind it (or every reason if all are keep)."""
    route = max((a.route for a in assessments), default="keep", key=ROUTES.index)
    if route == "keep":
        return route, sorted({r for a in assessments for r in a.reasons})
    return route, sorted({r for a in assessments if a.route != "keep" for r in a.reasons})


def _split(text: str, segment_letters: int, min_letters: int) -> list[tuple[int | None, int, str]]:
    """(page, first line number, text) pieces. Pages come from form feeds (pdftotext)."""
    if "\f" in text:
        pieces, line = [], 1
        for number, page in enumerate(text.split("\f"), start=1):
            if page.strip():
                pieces.append((number, line, page))
            line += page.count("\n")
        return pieces

    pieces: list[tuple[int | None, int, str]] = []
    lines = text.split("\n")
    start, letters = 0, 0
    for i, line in enumerate(lines):
        letters += len(letters_only(line).replace(BOUNDARY, ""))
        if letters >= segment_letters:
            pieces.append((None, start + 1, "\n".join(lines[start : i + 1])))
            start, letters = i + 1, 0
    rest = "\n".join(lines[start:])
    if rest.strip():
        if pieces and letters < min_letters:
            # Too short to judge alone: fold the tail into the previous piece.
            _, first, previous = pieces.pop()
            pieces.append((None, first, previous + "\n" + rest))
        else:
            pieces.append((None, start + 1, rest))
    return pieces


def assess_document(
    text: str,
    *,
    order_known: bool = True,
    segment_letters: int = SEGMENT_LETTERS,
    models: ModelPair | None = None,
    thresholds: Thresholds | None = None,
) -> TextReport:
    """Assess a whole extracted document page by page, so a few bad pages are not averaged
    away. Text with form feeds is split into pages; other text into runs of whole lines
    holding at least `segment_letters` Arabic letters."""
    models = models or default_models()
    t = thresholds or default_thresholds()
    segments = []
    for index, (page, first, piece) in enumerate(_split(text, segment_letters, t.min_letters)):
        assessment = assess_text(piece, order_known=order_known, models=models, thresholds=t)
        last = first + piece.rstrip("\n").count("\n")
        segments.append(Segment(index, page, first, last, assessment))
    decisive = [s.assessment for s in segments if s.assessment.decisive]
    route, reasons = worst(decisive or [s.assessment for s in segments])
    return TextReport(route, reasons, segments)
