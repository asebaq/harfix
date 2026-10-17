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
from .repair import Change, RepairResult, repair_text

__all__ = [
    "ROUTES",
    "Assessment",
    "Change",
    "CharLM",
    "DocumentReport",
    "FontReport",
    "HarfixError",
    "PageReport",
    "RepairResult",
    "Segment",
    "TextReport",
    "Thresholds",
    "assess_document",
    "assess_text",
    "repair_text",
    "scan_pdf",
]
__version__ = "0.2.0"
