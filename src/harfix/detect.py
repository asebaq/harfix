"""Turn character statistics and model scores into a keep / repair / reextract / ocr verdict."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from importlib import resources

from .model import ModelPair, default_models
from .normalize import BOUNDARY, letters_only, profile, strip_decorations

# Ordered from least to most severe; a page takes the most severe route of its parts.
ROUTES = ("keep", "repair", "reextract", "ocr")
_MIN_LINE_LETTERS = 20


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
    transposition_ratio: float = 0.27
    mixed_order_min_share: float = 0.2

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
    decisions: list[bool | None] = []  # True = visual (reversed) line
    visual_letters = logical_letters = 0
    for line in lines:
        n = len(line.replace(BOUNDARY, ""))
        if n < _MIN_LINE_LETTERS:
            decisions.append(None)
            continue
        forward, _ = model.bits_per_char(line)
        backward, _ = model.bits_per_char(line[::-1])
        if forward - backward > margin:
            decisions.append(True)
            visual_letters += n
        elif backward - forward > margin:
            decisions.append(False)
            logical_letters += n
        else:
            decisions.append(None)

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
    depends on the extractor; reading-order faults are not reported then.
    """
    models = models or default_models()
    t = thresholds or default_thresholds()
    prof = profile(text)
    metrics: dict[str, float | int | str] = {
        "arabic_letters": prof.arabic_letters,
        "arabic_ratio": round(prof.arabic_ratio, 4),
        "presentation_form_ratio": round(prof.presentation_form_ratio, 4),
        "unmapped_ratio": round(prof.unmapped_ratio, 4),
        "legacy_ratio": round(prof.legacy_ratio, 4),
        "bidi_controls": prof.bidi_controls,
    }
    reasons: list[str] = []
    route = "keep"

    def flag(reason: str, new_route: str) -> None:
        nonlocal route
        reasons.append(reason)
        if ROUTES.index(new_route) > ROUTES.index(route):
            route = new_route

    # Both are visible even when too few Arabic letters survive to score.
    if prof.unmapped >= t.unmapped_min_glyphs and prof.unmapped_ratio > t.unmapped_ratio:
        flag("unmapped_glyphs", "ocr")
    if (
        prof.visible >= t.legacy_min_visible
        and prof.arabic_ratio < 0.2
        and prof.legacy_ratio > t.legacy_ratio
    ):
        flag("legacy_encoding", "ocr")

    m = measure(text, models, t)
    metrics["arabic_letters"] = m.letters
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
    spiky = m.letters >= t.spike_min_letters and m.spike_rate > t.spike_rate
    implausible = m.bits > t.substitution_bits or spiky
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
