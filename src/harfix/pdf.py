"""Scan a PDF's text layer page by page and font by font."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

from pdfminer.high_level import extract_pages
from pdfminer.layout import LTAnno, LTChar, LTContainer, LTImage, LTPage, LTTextLine
from pdfminer.pdfparser import PDFSyntaxError
from pdfminer.psparser import PSException

from .detect import ROUTES, Assessment, Thresholds, assess_text, default_thresholds, worst
from .model import ModelPair, default_models


class HarfixError(Exception):
    """Raised when a document cannot be scanned."""


@dataclass
class FontReport:
    # The PDF font name, subset tag included: two subsets of one typeface are separate
    # embedded fonts and can carry different glyph-to-Unicode maps.
    font: str
    assessment: Assessment
    # "page": judged on this page's text. "document": too little text on this page, so
    # judged on this font's short runs pooled across every scanned page.
    scope: str = "page"

    def to_dict(self) -> dict:
        return {"font": self.font, "scope": self.scope, **self.assessment.to_dict()}


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


@dataclass
class _Page:
    number: int
    runs: dict[str, str]
    has_images: bool
    assessments: dict[str, Assessment]


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

    def assess(text: str) -> Assessment:
        return assess_text(text, order_known=False, models=models, thresholds=t)

    page_numbers = sorted({p - 1 for p in pages}) if pages is not None else None
    scanned: list[_Page] = []
    try:
        for index, layout in enumerate(extract_pages(str(path), page_numbers=page_numbers)):
            number = page_numbers[index] + 1 if page_numbers is not None else index + 1
            runs, has_images = _collect_page(layout)
            assessments = {font: assess(text) for font, text in runs.items()}
            scanned.append(_Page(number, runs, has_images, assessments))
    except (PDFSyntaxError, PSException, ValueError, KeyError) as error:
        raise HarfixError(f"Cannot read PDF {path}: {error}") from error

    # A font's ToUnicode map is the same on every page, so runs too short to judge on their
    # own (headings, running heads, verse numbers) are judged together.
    short: dict[str, list[str]] = defaultdict(list)
    for page in scanned:
        for font, a in page.assessments.items():
            if not a.decisive:
                short[font].append(page.runs[font])
    pooled = {font: assess("\n".join(texts)) for font, texts in short.items() if len(texts) > 1}

    return DocumentReport(str(path), [_report(page, pooled, assess) for page in scanned])


def _report(
    page: _Page, pooled: dict[str, Assessment], assess: Callable[[str], Assessment]
) -> PageReport:
    fonts = []
    for font, a in page.assessments.items():
        whole = pooled.get(font)
        if not a.decisive and whole and whole.decisive:
            fonts.append(FontReport(font, whole, "document"))
        else:
            fonts.append(FontReport(font, a))
    fonts.sort(key=lambda f: -int(f.assessment.metrics.get("arabic_letters", 0)))

    if not any(text.strip() for text in page.runs.values()):
        if page.has_images:
            return PageReport(page.number, "ocr", ["no_text_layer"], True, fonts)
        return PageReport(page.number, "keep", ["blank_page"], False, fonts)

    decisive = [f.assessment for f in fonts if f.assessment.decisive]
    if not decisive:
        # Every font run is short; judge the page's text as a whole instead.
        decisive = [assess("\n".join(page.runs.values()))]
    route, reasons = worst(decisive)
    return PageReport(page.number, route, reasons, page.has_images, fonts)


def _collect_page(layout: LTPage) -> tuple[dict[str, str], bool]:
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
    return {font: "".join(chunks) for font, chunks in runs.items()}, has_images


def _walk(container: LTContainer) -> Iterator:
    for item in container:
        yield item
        if isinstance(item, LTContainer) and not isinstance(item, LTTextLine):
            yield from _walk(item)


def _font_name(char: LTChar) -> str:
    return char.fontname or "unknown"


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
