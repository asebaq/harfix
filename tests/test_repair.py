from conftest import CLEAN, CLEAN_LINES, isolated_forms, permute_letters

from harfix import repair_text
from harfix.cli import main


def visual(lines: list[str]) -> str:
    return "\n".join(line[::-1] for line in lines)


def test_visual_order_lines_are_reversed_keeping_numbers_latin_and_brackets():
    # As a visual-order extractor emits it: words right to left, but digits and Latin
    # left to right, and brackets by their drawn shape.
    shown = "2019 ةنسل harfix tool (12) ةداملا فدهت"
    result = repair_text(shown + "\n" + visual(CLEAN_LINES))
    first, *rest = result.text.split("\n")
    assert first == "تهدف المادة (12) harfix tool لسنة 2019"
    assert rest == CLEAN_LINES
    assert [(c.reason, c.count) for c in result.changes] == [("visual_order", 7)]


def test_presentation_forms_are_decomposed_but_latin_ligatures_are_not():
    text = isolated_forms(CLEAN) + "\n\ufb01le"
    result = repair_text(text)
    assert result.text == CLEAN + "\n\ufb01le"
    assert [c.reason for c in result.changes] == ["presentation_forms"]


def test_unmapped_elongation_glyphs_are_deleted():
    result = repair_text(CLEAN.replace("ما", "م\ufffd\ufffdا"))
    assert result.text == CLEAN
    assert [c.reason for c in result.changes] == ["unmapped_elongation"]


def test_bidi_controls_are_deleted_without_gluing_words():
    # pdftotext wraps script changes in embedding marks (U+202A-U+202C).
    lines = [f"\u202b{line}\u202c" for line in CLEAN_LINES]
    lines.append("\u202bالموقع الإلكتروني\u202ahindawi.org\u202c")
    result = repair_text("\n".join(lines))
    assert result.text == "\n".join([*CLEAN_LINES, "الموقع الإلكتروني hindawi.org"])
    assert [c.reason for c in result.changes] == ["bidi_controls"]


def test_pages_that_need_ocr_are_left_alone_and_reported():
    broken = permute_letters(CLEAN)
    text = "\f".join([visual(CLEAN_LINES), broken, CLEAN]) + "\f"
    result = repair_text(text)
    assert result.text.split("\f") == [CLEAN, broken, CLEAN, ""]
    assert [(s.page, s.assessment.route) for s in result.unrepaired] == [(2, "ocr")]


def test_repairing_twice_changes_nothing_more():
    once = repair_text(isolated_forms(visual(CLEAN_LINES))).text
    assert once == CLEAN
    assert repair_text(once).changes == []


def test_cli_writes_repaired_text_and_reports_changes(tmp_path, capsys):
    source = tmp_path / "extracted.txt"
    source.write_text(isolated_forms(CLEAN), encoding="utf-8")
    target = tmp_path / "repaired.txt"
    assert main(["repair", str(source), "-o", str(target)]) == 0
    assert target.read_text(encoding="utf-8") == CLEAN
    assert "presentation_forms" in capsys.readouterr().err
