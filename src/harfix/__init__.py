"""harfix: find Arabic PDF text that will silently poison a search index."""

from .detect import (
    ROUTES,
    Assessment,
    Segment,
    TextReport,
    Thresholds,
    assess_document,
    assess_text,
)
from .model import CharLM
from .pdf import DocumentReport, FontReport, HarfixError, PageReport, scan_pdf

__all__ = [
    "ROUTES",
    "Assessment",
    "CharLM",
    "DocumentReport",
    "FontReport",
    "HarfixError",
    "PageReport",
    "Segment",
    "TextReport",
    "Thresholds",
    "assess_document",
    "assess_text",
    "scan_pdf",
]
__version__ = "0.1.0"
