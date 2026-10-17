"""Deterministic repairs for text that `assess_document` routes to `repair`.

Only segments whose route is `repair` are changed, and only for the reasons found in them:

- `bidi_controls`: delete bidi formatting characters (a space where they joined words).
- `unmapped_elongation`: delete U+FFFD between Arabic letters.
- `visual_order`: reverse each Arabic line, keeping left-to-right runs (numbers, Latin
  words) in their own order and mirroring brackets.
- `presentation_forms`: decompose presentation forms with NFKC.

Segments that need `reextract` or `ocr` are left as they are: their letters cannot be
trusted, so no text-level fix makes them safe to index.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from .detect import Segment, Thresholds, assess_document, default_thresholds, line_direction
from .model import ModelPair, default_models
from .normalize import (
    decompose_presentation_forms,
    drop_bidi_controls,
    drop_inner_replacement,
    letters_only,
    strip_decorations,
)

# Left-to-right runs inside a right-to-left line: digits (Western, Arabic-Indic, Persian)
# and Latin words, joined by the separators that stay inside numbers and phrases.
_LTR_RUN = re.compile(
    r"[A-Za-z0-9\u0660-\u0669\u06F0-\u06F9]+"
    r"(?:[ .,:/\-_%]+[A-Za-z0-9\u0660-\u0669\u06F0-\u06F9]+)*"
)
_MIRROR = str.maketrans("()[]{}<>«»", ")(][}{><»«")
_EDGES = re.compile(r"^(\s*)(.*?)(\s*)$", re.S)


@dataclass
class Change:
    reason: str
    page: int | None
    start_line: int
    end_line: int
    # Characters deleted or decomposed, or lines reversed.
    count: int

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RepairResult:
    text: str
    changes: list[Change]
    # Segments routed to `reextract` or `ocr`: left unchanged.
    unrepaired: list[Segment]

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "changes": [c.to_dict() for c in self.changes],
            "unrepaired": [s.to_dict() for s in self.unrepaired],
        }


def reverse_visual_line(line: str) -> str:
    """Turn one line from visual (display) order into logical order."""
    head, body, tail = _EDGES.match(line).groups()
    flipped = body[::-1].translate(_MIRROR)
    return head + _LTR_RUN.sub(lambda m: m.group()[::-1], flipped) + tail


def _reverse_lines(text: str, models: ModelPair, t: Thresholds) -> tuple[str, int]:
    out, reversed_lines = [], 0
    for line in text.split("\n"):
        letters, _ = strip_decorations(letters_only(line))
        # Lines without Arabic were extracted left to right already; lines that read
        # forwards on their own are in logical order already.
        if letters and line_direction(letters, models.spaced, t.orientation_margin) is not False:
            line = reverse_visual_line(line)
            reversed_lines += 1
        out.append(line)
    return "\n".join(out), reversed_lines


def _repair_piece(text: str, reasons: list[str], models: ModelPair, t: Thresholds):
    done: list[tuple[str, int]] = []
    if "bidi_controls" in reasons:
        text, n = drop_bidi_controls(text)
        done.append(("bidi_controls", n))
    if "unmapped_elongation" in reasons:
        text, n = drop_inner_replacement(text)
        done.append(("unmapped_elongation", n))
    # Reverse before decomposing: a lam-alef ligature is one character in visual order
    # and must become two letters in logical order.
    if "visual_order" in reasons:
        text, n = _reverse_lines(text, models, t)
        done.append(("visual_order", n))
    if "presentation_forms" in reasons:
        text, n = decompose_presentation_forms(text)
        done.append(("presentation_forms", n))
    return text, done


def repair_text(
    text: str,
    *,
    models: ModelPair | None = None,
    thresholds: Thresholds | None = None,
) -> RepairResult:
    """Assess `text` page by page (as `assess_document` does) and repair what is safe."""
    models = models or default_models()
    t = thresholds or default_thresholds()
    report = assess_document(text, models=models, thresholds=t)
    changes: list[Change] = []
    unrepaired = [s for s in report.segments if s.assessment.route in ("reextract", "ocr")]

    def fix(segment: Segment, piece: str) -> str:
        if segment.assessment.route != "repair":
            return piece
        piece, done = _repair_piece(piece, segment.assessment.reasons, models, t)
        changes.extend(
            Change(reason, segment.page, segment.start_line, segment.end_line, n)
            for reason, n in done
            if n
        )
        return piece

    if "\f" in text:
        pages = text.split("\f")
        for segment in report.segments:
            pages[segment.page - 1] = fix(segment, pages[segment.page - 1])
        return RepairResult("\f".join(pages), changes, unrepaired)

    lines = text.split("\n")
    for segment in report.segments:
        first, last = segment.start_line - 1, segment.end_line
        piece = fix(segment, "\n".join(lines[first:last]))
        lines[first:last] = piece.split("\n")
    return RepairResult("\n".join(lines), changes, unrepaired)
