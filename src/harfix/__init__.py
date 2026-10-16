"""harfix: find Arabic PDF text that will silently poison a search index."""

from .detect import ROUTES, Assessment, Thresholds, assess_text
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
    "Thresholds",
    "assess_text",
    "scan_pdf",
]
__version__ = "0.1.0.dev0"
