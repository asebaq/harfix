"""harfix: find Arabic PDF text that will silently poison a search index."""

from .decode import DecodedPage, FontMap, decode_pdf
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
    "DecodedPage",
    "DocumentReport",
    "FontReport",
    "FontMap",
    "HarfixError",
    "PageReport",
    "RepairResult",
    "Segment",
    "TextReport",
    "Thresholds",
    "assess_document",
    "assess_text",
    "decode_pdf",
    "repair_text",
    "scan_pdf",
]
__version__ = "0.6.0"
