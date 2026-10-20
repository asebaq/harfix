import random

from conftest import CLEAN, CLEAN_LINES, NAMES

from harfix import assess_text, repair_text

FORMS = ["isolated", "initial", "medial", "final"]


def glyph_names(line: str, rng: random.Random) -> str:
    """A line as docling-parse writes a font without a Unicode map: one glyph name per
    glyph, glued per word, glyphs left to right across the page (visual order)."""
    words = []
    for word in line.split():
        glyphs, i = [], 0
        while i < len(word):
            if word.startswith("لا", i):
                glyphs.append("lamwithalef" + rng.choice(FORMS))
                i += 2
                continue
            glyphs.append(NAMES[word[i]] + rng.choice(FORMS))
            i += 1
        words.append("".join(reversed(glyphs)))
    return " ".join(reversed(words))


def test_glyph_names_are_spelled_out_in_reading_order():
    rng = random.Random(3)
    text = "\n".join(glyph_names(line, rng) for line in CLEAN_LINES)
    verdict = assess_text(text)
    assert (verdict.route, verdict.reasons) == ("repair", ["glyph_names"])
    assert repair_text(text).text == CLEAN


def test_glyph_names_of_a_wrong_map_are_still_sent_to_ocr():
    # Names that spell letters which do not form Arabic words: the font itself is wrong.
    rng = random.Random(5)
    letters = list(NAMES)
    swap = dict(zip(letters, rng.sample(letters, len(letters)), strict=True))
    scrambled = ["".join(swap.get(c, c) for c in line) for line in CLEAN_LINES]
    verdict = assess_text("\n".join(glyph_names(line, rng) for line in scrambled))
    assert verdict.route == "ocr"
    assert "glyph_names" in verdict.reasons


def test_english_words_that_are_also_letter_names_are_left_alone():
    text = "We have seen a sad dad wait for the teh test results, " * 6
    verdict = assess_text(text)
    assert "glyph_names" not in verdict.reasons
    assert repair_text(text).text == text


def test_glyph_codes_written_as_numbers_go_to_ocr_but_page_numbers_and_tables_do_not():
    # docling-parse writes each glyph of a font with neither a Unicode map nor glyph
    # names as its code: one number per glyph, the same number for the same letter.
    rng = random.Random(9)
    code = {letter: str(rng.randint(30, 230)) for letter in NAMES}
    codes = "\n".join(" ".join(code[c] for c in line if c in code) for line in CLEAN_LINES)
    verdict = assess_text(codes)
    assert (verdict.route, verdict.reasons) == ("ocr", ["unmapped_glyphs"])

    page_numbers = "\n".join(str(n) for n in range(101, 141))
    assert "unmapped_glyphs" not in assess_text(page_numbers).reasons
    years = "\n".join("2023 2024 2023 2024 2023 2024" for _ in range(8))
    assert "unmapped_glyphs" not in assess_text(years).reasons
    table = "\n".join(
        f"عدد الطلاب المسجلين في السنة {year} {rng.randint(100, 999)} {rng.randint(100, 999)}"
        for year in range(1990, 2010)
    )
    assert "unmapped_glyphs" not in assess_text(table).reasons


def test_a_legacy_font_split_into_one_character_per_word_goes_to_ocr():
    # Extractors that break text at every font change write a pre-Unicode font that
    # spreads each word over several subsets as single ASCII characters.
    from conftest import ascii_legacy

    fragments = " ".join(ascii_legacy(CLEAN).replace(" ", ""))
    verdict = assess_text(fragments)
    assert (verdict.route, verdict.reasons) == ("ocr", ["legacy_encoding"])

    dot_leaders = "\n".join(f"Chapter {i} " + ". " * 40 + str(i * 7) for i in range(1, 8))
    assert assess_text(dot_leaders).route == "keep"
