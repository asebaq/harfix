from conftest import ASCII_LEGACY, CLEAN_LINES, NAMES
from pdf_fixture import LETTERS, build_pdf

from harfix import scan_pdf
from harfix.cli import main
from harfix.decode import GAP_NARROW, GAP_WIDE, SPACE, FontMap, decode_pdf

# A pre-Unicode font: every Arabic letter is drawn from an ASCII code.
LEGACY_MAP = FontMap(
    {
        **{f"Legacy:{code}": [(letter, 0.0)] for letter, code in ASCII_LEGACY.items()},
        GAP_WIDE: [(SPACE, 0.0)],
        GAP_NARROW: [(SPACE, 0.0)],
        SPACE: [(SPACE, 0.0)],
    },
    {},
)


def legacy_pdf(tmp_path):
    # Right-to-left text is drawn right to left: the first letter of a line is rightmost.
    pages = [[("Legacy", line[::-1]) for line in CLEAN_LINES]]
    path = tmp_path / "legacy.pdf"
    path.write_bytes(build_pdf(pages, {"Legacy": ASCII_LEGACY}))
    return path


def test_known_legacy_font_is_decoded_and_passes_the_check(tmp_path):
    page = decode_pdf(legacy_pdf(tmp_path), font_map=LEGACY_MAP)[0]
    assert page.text.split("\n") == CLEAN_LINES
    assert page.known_share == 1.0
    assert page.trusted


def test_pages_in_fonts_the_map_does_not_know_are_not_decoded(tmp_path):
    path = tmp_path / "unicode.pdf"
    identity = {letter: letter for letter in LETTERS}
    path.write_bytes(
        build_pdf([[("Naskh", line[::-1]) for line in CLEAN_LINES]], {"Naskh": identity})
    )
    page = decode_pdf(path, font_map=LEGACY_MAP)[0]
    assert (page.text, page.assessment, page.trusted) == ("", None, False)


def test_a_wrong_font_map_is_caught_by_the_check(tmp_path):
    shifted = dict(zip(LETTERS, LETTERS[1:] + LETTERS[:1], strict=True))
    wrong = FontMap(
        {
            **{f"Legacy:{ASCII_LEGACY[a]}": [(b, 0.0)] for a, b in shifted.items()},
            GAP_WIDE: [(SPACE, 0.0)],
            SPACE: [(SPACE, 0.0)],
        },
        {},
    )
    page = decode_pdf(legacy_pdf(tmp_path), font_map=wrong)[0]
    assert page.assessment is not None
    assert not page.trusted


def test_cli_decodes_with_the_packaged_map_and_reports_pages(tmp_path, capsys):
    # The packaged map does not know the test font: the page is reported, not guessed.
    out = tmp_path / "decoded.txt"
    assert main(["decode", str(legacy_pdf(tmp_path)), "-o", str(out)]) == 0
    assert out.read_text(encoding="utf-8") == ""
    assert "not decoded p1" in capsys.readouterr().err


def test_a_font_whose_glyphs_are_named_is_decoded_with_the_packaged_map(tmp_path):
    # No Unicode map, but the encoding names each glyph (`qafisolated`): the names spell
    # the letters, whatever fonts the packaged map was learned from.
    names = {letter: NAMES[letter] + "isolated" for letter in LETTERS if letter in NAMES}
    pages = [[("Named", line[::-1]) for line in CLEAN_LINES]]
    path = tmp_path / "named.pdf"
    path.write_bytes(build_pdf(pages, {}, glyph_names={"Named": names}))
    page = decode_pdf(path)[0]
    assert page.text.split("\n") == CLEAN_LINES
    assert page.trusted


def test_text_in_unicode_fonts_on_a_decoded_page_is_kept(tmp_path):
    # A heading and a page number set in a Unicode font above a legacy-font body.
    identity = {letter: letter for letter in LETTERS}
    heading = "الفصل الأول"
    pages = [[("Naskh", heading[::-1]), *[("Legacy", line[::-1]) for line in CLEAN_LINES]]]
    path = tmp_path / "mixed.pdf"
    path.write_bytes(build_pdf(pages, {"Legacy": ASCII_LEGACY, "Naskh": identity}))
    page = decode_pdf(path, font_map=LEGACY_MAP)[0]
    assert page.text.split("\n") == [heading, *CLEAN_LINES]
    assert page.trusted


def test_scan_points_to_decode_for_fonts_it_can_read(tmp_path):
    names = {letter: NAMES[letter] + "isolated" for letter in LETTERS if letter in NAMES}
    named = tmp_path / "named.pdf"
    named.write_bytes(
        build_pdf([[("Named", line[::-1]) for line in CLEAN_LINES]], {}, {"Named": names})
    )
    assert scan_pdf(named).pages[0].decodable
    # A legacy font no map knows is sent to OCR without a pointer to `decode`.
    page = scan_pdf(legacy_pdf(tmp_path)).pages[0]
    assert page.route == "ocr" and not page.decodable
