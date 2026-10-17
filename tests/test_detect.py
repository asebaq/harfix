import pytest
from conftest import CLEAN, CLEAN_LINES, ascii_legacy, isolated_forms, permute_letters

from harfix import assess_document, assess_text
from harfix.normalize import letters_only


def reverse_lines(text: str) -> str:
    return "\n".join(line[::-1] for line in text.splitlines())


@pytest.mark.parametrize("order_known", [True, False])
def test_clean_arabic_is_kept(clean_text, order_known):
    result = assess_text(clean_text, order_known=order_known)
    assert result.route == "keep"
    assert result.reasons == []
    assert result.sufficient


def test_visual_order_is_repairable_in_extractor_output(clean_text):
    result = assess_text(reverse_lines(clean_text))
    assert result.route == "repair"
    assert result.reasons == ["visual_order"]


def test_visual_order_is_not_a_fault_of_a_pdf_text_layer(clean_text):
    assert assess_text(reverse_lines(clean_text), order_known=False).route == "keep"


@pytest.mark.parametrize("order_known", [True, False])
def test_wrong_letter_mapping_needs_ocr_in_either_reading_direction(clean_text, order_known):
    for text in (permute_letters(clean_text), reverse_lines(permute_letters(clean_text))):
        result = assess_text(text, order_known=order_known)
        assert result.route == "ocr"
        assert "same_script_substitution" in result.reasons


def test_inserted_padding_letters_need_ocr(clean_text):
    padded = "".join(ch + "مم" if ch in "ابتكلن" else ch for ch in clean_text)
    assert assess_text(padded, order_known=False).reasons == ["same_script_substitution"]


def test_presentation_forms_are_repairable(clean_text):
    result = assess_text(isolated_forms(clean_text))
    assert result.route == "repair"
    assert result.reasons == ["presentation_forms"]


def test_lam_alef_transposition_needs_reextraction(clean_text):
    swapped = " ".join(
        "ا" + w[2] + "ل" + w[3:] if w.startswith("ال") and len(w) > 3 else w
        for w in clean_text.split(" ")
    )
    result = assess_text(swapped)
    assert result.route == "reextract"
    assert "lam_alef_transposition" in result.reasons


def test_alternating_line_directions_are_mixed_order():
    mixed = "\n".join(line[::-1] if i % 2 else line for i, line in enumerate(CLEAN_LINES))
    result = assess_text(mixed)
    assert result.route == "reextract"
    assert "mixed_reading_order" in result.reasons


def test_words_split_into_fragments_need_reextraction(clean_text):
    fragments = " ".join(
        " ".join(word[i : i + 2] for i in range(0, len(word), 2)) for word in clean_text.split(" ")
    )
    result = assess_text(fragments)
    assert result.route == "reextract"
    assert result.reasons == ["lost_word_boundaries"]


def test_legacy_encoded_font_needs_ocr():
    legacy = "≤∞±≥ WM d L u ≤¥ v —dJ ¥∑ œbF« ≠ WOLd« …bd'« W}dF« dB W|—uNL f}z— —«d"
    result = assess_text(legacy, order_known=False)
    assert result.route == "ocr"
    assert result.reasons == ["legacy_encoding"]


def test_arabic_font_encoded_as_ascii_letters_needs_ocr(clean_text):
    result = assess_text(ascii_legacy(clean_text), order_known=False)
    assert (result.route, result.reasons) == ("ocr", ["legacy_encoding"])


def test_english_prose_is_not_mistaken_for_a_legacy_font():
    english = (
        "This library checks Arabic text extracted from PDF files before it is indexed. "
        "The NATO and UNESCO reports cited in Appendix IV are quoted in English."
    )
    assert assess_text(english, order_known=False).route == "keep"


def test_arabic_font_encoded_as_ascii_digits_and_punctuation_needs_ocr(clean_text):
    # Some pre-Unicode fonts put Arabic glyphs on digit and punctuation codes only.
    symbols = "0123456789!#$%&)*+,-./:;<=>?@[]^_{|}~"
    codes = dict(zip(sorted(set(letters_only(clean_text)) - {" "}), symbols, strict=False))
    legacy = "".join(codes.get(ch, ch) for ch in letters_only(clean_text))
    result = assess_text(legacy, order_known=False)
    assert (result.route, result.reasons) == ("ocr", ["legacy_encoding"])


def test_numbers_dates_and_percentages_are_not_a_legacy_font():
    numbers = " ".join(["12-15", "1990/3/12", "15%", "(1)", "[3]", "1/2", "$100", "+5", "45."] * 4)
    assert assess_text(numbers, order_known=False).route == "keep"


def test_unmapped_elongation_glyphs_inside_intact_words_are_repairable(clean_text):
    # Kashida glyphs without a Unicode mapping extract as U+FFFD between letters.
    stretched = clean_text.replace("ما", "م\ufffd\ufffdا").replace("لت", "ل\ufffdت")
    result = assess_text(stretched, order_known=False)
    assert (result.route, result.reasons) == ("repair", ["unmapped_elongation"])


def test_unmapped_glyphs_that_replace_letters_still_need_ocr(clean_text):
    lost = " ".join(
        "".join("\ufffd" if i % 3 == 1 and 0 < i < len(w) - 1 else c for i, c in enumerate(w))
        for w in clean_text.split(" ")
    )
    assert assess_text(lost, order_known=False).route == "ocr"


def test_quran_glyph_codes_are_not_sent_to_unicode_repair(clean_text):
    # One Presentation Forms-A code point per word, as in King Fahd Complex page fonts.
    verse = " ".join(chr(0xFB51 + i) for i in range(30))
    result = assess_text(clean_text + "\n" + verse)
    assert (result.route, result.reasons) == ("ocr", ["quran_glyph_codes"])
    # The surrounding text is still judged on its own letters.
    assert result.sufficient


def test_stray_ligature_glyphs_are_not_mistaken_for_quran_fonts():
    # Ordinary font ligatures (as in Lotus) are not numbered in reading order.
    ligatures = "\n".join(chr(0xFC0A + 37 * i) for i in range(12))
    assert "quran_glyph_codes" not in assess_text(ligatures, order_known=False).reasons


def test_ornate_parentheses_around_quotations_are_not_quran_glyph_codes(clean_text):
    # ﴿…﴾ (U+FD3F/U+FD3E) are punctuation in the presentation-forms block, and empty pairs
    # alternate between adjacent code points just like numbered glyph IDs.
    quoted = "\n".join(f"{line} ﴿ ﴾ [البقرة: 87] ﴿ ﴾" for line in clean_text.splitlines())
    result = assess_text(quoted, order_known=False)
    assert (result.route, result.reasons) == ("keep", [])


def test_short_text_is_not_judged():
    result = assess_text("المادة الأولى")
    assert result.route == "keep"
    assert not result.sufficient
    assert result.reasons == ["insufficient_arabic_text"]


def test_unmapped_glyphs_are_flagged_even_without_arabic_letters():
    result = assess_text("\ue001\ue002\ue003\ue004\ue005\ue006 abc")
    assert result.route == "ocr"
    assert result.reasons == ["unmapped_glyphs"]


def test_one_broken_page_is_not_averaged_away_by_clean_pages():
    pages = [CLEAN] * 8 + [permute_letters(CLEAN)] + [CLEAN]
    text = "\f".join(pages) + "\f"
    assert assess_text(text).route == "keep"  # whole-document score is diluted

    report = assess_document(text)
    assert (report.route, report.reasons) == ("ocr", ["same_script_substitution"])
    assert [s.page for s in report.segments if s.assessment.route != "keep"] == [9]


def test_text_without_page_breaks_is_judged_in_line_ranges():
    text = "\n".join([CLEAN] * 4 + [permute_letters(CLEAN)] + [CLEAN] * 4)
    report = assess_document(text, segment_letters=300)
    flagged = [s for s in report.segments if s.assessment.route != "keep"]
    assert report.route == "ocr"
    broken_lines = range(4 * len(CLEAN_LINES) + 1, 5 * len(CLEAN_LINES) + 1)
    assert flagged
    assert all(
        s.start_line <= broken_lines.stop - 1 and s.end_line >= broken_lines.start for s in flagged
    )


def test_short_tail_is_judged_with_the_previous_segment():
    text = "\n".join([CLEAN] * 3 + [permute_letters(CLEAN_LINES[1])])
    report = assess_document(text, segment_letters=300)
    assert report.route == "ocr"
    assert all(s.assessment.sufficient for s in report.segments)
