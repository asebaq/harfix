import argparse
import json

import pytest
from conftest import permute_letters

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
