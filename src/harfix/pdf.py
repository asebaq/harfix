"""Scan a PDF's text layer page by page and font by font."""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

from pdfminer.high_level import extract_pages
from pdfminer.layout import LTAnno, LTChar, LTContainer, LTImage, LTPage, LTTextLine
from pdfminer.pdfparser import PDFSyntaxError
from pdfminer.psparser import PSException

from .detect import ROUTES, Assessment, Thresholds, assess_text, default_thresholds
from .model import ModelPair, default_models

_SUBSET_PREFIX = re.compile(r"^[A-Z]{6}\+")


class HarfixError(Exception):
    """Raised when a document cannot be scanned."""


@dataclass
class FontReport:
    font: str
    assessment: Assessment

    def to_dict(self) -> dict:
        return {"font": self.font, **self.assessment.to_dict()}


@dataclass
class PageReport:
    page: int
    route: str
    reasons: list[str]
    has_images: bool
    fonts: list[FontReport] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "page": self.page,
            "route": self.route,
            "reasons": self.reasons,
            "has_images": self.has_images,
            "fonts": [f.to_dict() for f in self.fonts],
        }


@dataclass
class DocumentReport:
    path: str
    pages: list[PageReport]

    @property
    def route_counts(self) -> dict[str, int]:
        counts = {route: 0 for route in ROUTES}
        for page in self.pages:
            counts[page.route] += 1
        return counts

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "route_counts": self.route_counts,
            "pages": [p.to_dict() for p in self.pages],
        }


def scan_pdf(
    path: str | Path,
    *,
    pages: Iterable[int] | None = None,
    models: ModelPair | None = None,
    thresholds: Thresholds | None = None,
) -> DocumentReport:
    """Assess every font run on the requested 1-based pages of a PDF."""
    models = models or default_models()
    t = thresholds or default_thresholds()
    page_numbers = sorted({p - 1 for p in pages}) if pages is not None else None
    reports = []
    try:
        for index, layout in enumerate(extract_pages(str(path), page_numbers=page_numbers)):
            number = page_numbers[index] + 1 if page_numbers is not None else index + 1
            reports.append(_scan_page(number, layout, models, t))
    except (PDFSyntaxError, PSException, ValueError, KeyError) as error:
        raise HarfixError(f"Cannot read PDF {path}: {error}") from error
    return DocumentReport(str(path), reports)


def _scan_page(number: int, layout: LTPage, models: ModelPair, t: Thresholds) -> PageReport:
    runs: dict[str, list[str]] = defaultdict(list)
    has_images = False
    for item in _walk(layout):
        if isinstance(item, LTImage):
            has_images = True
        elif isinstance(item, LTTextLine):
            _collect_line(item, runs)
        elif isinstance(item, LTChar):
            # Characters inside figures are not grouped into lines by pdfminer.
            runs[_font_name(item)].append(item.get_text())

    fonts = [
        FontReport(
            font, assess_text("".join(chunks), order_known=False, models=models, thresholds=t)
        )
        for font, chunks in runs.items()
    ]
    fonts.sort(key=lambda f: -int(f.assessment.metrics.get("arabic_letters", 0)))

    if not any("".join(chunks).strip() for chunks in runs.values()):
        if has_images:
            return PageReport(number, "ocr", ["no_text_layer"], True, fonts)
        return PageReport(number, "keep", ["blank_page"], False, fonts)

    decisive = [
        f.assessment for f in fonts if f.assessment.sufficient or f.assessment.route != "keep"
    ]
    if not decisive:
        # Each font run is short; judge the page's text as a whole instead.
        whole = assess_text(
            "\n".join("".join(c) for c in runs.values()),
            order_known=False,
            models=models,
            thresholds=t,
        )
        decisive = [whole]

    route = max((a.route for a in decisive), key=ROUTES.index)
    reasons = sorted({r for a in decisive for r in a.reasons if a.route != "keep"})
    if route == "keep":
        reasons = sorted({r for a in decisive for r in a.reasons})
    return PageReport(number, route, reasons, has_images, fonts)


def _walk(container: LTContainer) -> Iterator:
    for item in container:
        yield item
        if isinstance(item, LTContainer) and not isinstance(item, LTTextLine):
            yield from _walk(item)


def _font_name(char: LTChar) -> str:
    return _SUBSET_PREFIX.sub("", char.fontname or "unknown")


def _collect_line(line: LTTextLine, runs: dict[str, list[str]]) -> None:
    current: str | None = None
    used: set[str] = set()
    for item in line:
        if isinstance(item, LTChar):
            current = _font_name(item)
            used.add(current)
            runs[current].append(item.get_text())
        elif isinstance(item, LTAnno) and current is not None:
            runs[current].append(" ")
    for font in used:
        runs[font].append("\n")
