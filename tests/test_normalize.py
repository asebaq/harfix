from conftest import isolated_forms

from harfix.normalize import letters_only, profile, strip_decorations


def test_presentation_forms_are_counted_raw_and_folded_for_scoring():
    shaped = isolated_forms("كتاب القانون")
    p = profile(shaped)
    assert p.presentation_forms == p.arabic_letters == 11
    assert letters_only(shaped) == "كتاب القانون"


def test_diacritics_tatweel_and_regional_letters_are_normalized():
    assert letters_only("مُحَـــمَّد کتاب") == "محمد كتاب"


def test_digits_latin_and_punctuation_become_single_boundaries():
    assert letters_only("المادة 248، من القانون (2020)") == "المادة من القانون"


def test_symbol_font_bullets_are_not_unmapped_glyphs():
    bullets = "\uf0b7 بند أول \uf0b7 بند ثان"
    assert profile(bullets).unmapped == 0
    assert profile("\ue001\ue002 نص").unmapped == 2


def test_pdfminer_cid_codes_count_as_unmapped():
    p = profile("(cid:4)(cid:27) W‡M (cid:19)")
    assert p.cid_codes == 3
    assert p.unmapped == 3


def test_legacy_symbol_text_is_measured_but_arabic_typography_is_not():
    legacy = profile("W‡M‡‡ ±¥≥µ Âd‡ ≤∞ —œUB ‰u‡‡‡‡B")
    assert legacy.legacy_ratio > 0.5
    assert profile("قال «نعم» – انتهى…").legacy_symbols == 0


def test_decoration_runs_are_removed_but_real_doubled_letters_stay():
    cleaned, runs = strip_decorations("المحكمة دددددددددددد الحكم مم")
    assert runs == 1
    assert cleaned == "المحكمة الحكم مم"
