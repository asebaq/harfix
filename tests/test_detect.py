import pytest
from conftest import CLEAN_LINES, isolated_forms, permute_letters

from harfix import assess_text


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


def test_short_text_is_not_judged():
    result = assess_text("المادة الأولى")
    assert result.route == "keep"
    assert not result.sufficient
    assert result.reasons == ["insufficient_arabic_text"]


def test_unmapped_glyphs_are_flagged_even_without_arabic_letters():
    result = assess_text("\ue001\ue002\ue003\ue004\ue005\ue006 abc")
    assert result.route == "ocr"
    assert result.reasons == ["unmapped_glyphs"]
