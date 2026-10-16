import random

import pytest
from conftest import CLEAN_LINES
from pdf_fixture import LETTERS, build_pdf

from harfix import HarfixError, scan_pdf

IDENTITY = {letter: letter for letter in LETTERS}
_shuffled = LETTERS[:]
random.Random(3).shuffle(_shuffled)
WRONG = dict(zip(LETTERS, _shuffled, strict=True))


@pytest.fixture
def pdf_path(tmp_path):
    pages = [
        [("Good", line) for line in CLEAN_LINES],
        [("Good", line) for line in CLEAN_LINES] + [("Broken", line) for line in CLEAN_LINES],
        [],
    ]
    path = tmp_path / "sample.pdf"
    path.write_bytes(build_pdf(pages, {"Good": IDENTITY, "Broken": WRONG}))
    return path


def test_scan_routes_each_page_by_its_worst_font(pdf_path):
    report = scan_pdf(pdf_path)
    assert [p.route for p in report.pages] == ["keep", "ocr", "ocr"]
    assert report.route_counts == {"keep": 1, "repair": 0, "reextract": 0, "ocr": 2}


def test_broken_font_is_isolated_from_healthy_font_on_the_same_page(pdf_path):
    page = scan_pdf(pdf_path, pages=[2]).pages[0]
    assert page.page == 2
    assert page.reasons == ["same_script_substitution"]
    routes = {f.font: f.assessment.route for f in page.fonts}
    assert routes == {"Good": "keep", "Broken": "ocr"}


def test_image_only_page_needs_ocr(pdf_path):
    page = scan_pdf(pdf_path, pages=[3]).pages[0]
    assert (page.route, page.reasons, page.has_images) == ("ocr", ["no_text_layer"], True)


def test_unreadable_file_raises_harfix_error(tmp_path):
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"not a pdf")
    with pytest.raises(HarfixError):
        scan_pdf(bad)
