import argparse
import json

import pytest
from conftest import permute_letters
from pdf_fixture import build_pdf

from harfix.cli import _parse_pages, main


def test_page_ranges_are_parsed_and_deduplicated():
    assert _parse_pages("3,1-2,2") == [1, 2, 3]


@pytest.mark.parametrize("spec", ["0", "5-2", "x"])
def test_invalid_page_ranges_are_rejected(spec):
    with pytest.raises((ValueError, argparse.ArgumentTypeError)):
        _parse_pages(spec)


def test_check_fails_only_at_or_above_the_requested_route(tmp_path, capsys, clean_text):
    garbled = tmp_path / "garbled.txt"
    garbled.write_text(permute_letters(clean_text), encoding="utf-8")

    assert main(["check", str(garbled), "--json", "--fail-on", "ocr"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["route"] == "ocr"

    clean = tmp_path / "clean.txt"
    clean.write_text(clean_text, encoding="utf-8")
    assert main(["check", str(clean), "--fail-on", "repair"]) == 0


def test_text_without_arabic_is_not_passed_as_clean(tmp_path, capsys):
    # Nothing was judged, so a gate must not let it through.
    english = tmp_path / "english.txt"
    english.write_text("The quick brown fox jumps over the lazy dog.\n", encoding="utf-8")
    assert main(["check", str(english)]) == 0
    assert main(["check", str(english), "--fail-on", "ocr"]) == 1
    assert "no Arabic text to judge" in capsys.readouterr().out


def test_unreadable_input_is_reported_without_a_traceback(tmp_path, capsys):
    latin1 = tmp_path / "latin1.txt"
    latin1.write_bytes("caf\xe9".encode("latin-1"))
    assert main(["check", str(latin1)]) == 2
    assert main(["scan", str(tmp_path)]) == 2
    err = capsys.readouterr().err
    assert "not UTF-8" in err and "Is a directory" in err


def test_pages_past_the_end_are_an_error(tmp_path, capsys):
    pdf = tmp_path / "one_page.pdf"
    pdf.write_bytes(build_pdf([[]], {}))
    assert main(["scan", "--pages", "3-4", str(pdf)]) == 2
    assert "has no page 3-4" in capsys.readouterr().err


def test_repair_fails_on_text_it_cannot_repair(tmp_path, clean_text):
    garbled = tmp_path / "garbled.txt"
    garbled.write_text(permute_letters(clean_text), encoding="utf-8")
    assert main(["repair", str(garbled), "-o", str(tmp_path / "out.txt")]) == 0
    assert main(["repair", str(garbled), "-o", str(tmp_path / "out.txt"), "--fail-on", "ocr"]) == 1
