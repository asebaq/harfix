# harfix check: one benchmark, three extractors

Generated 2026-10-21 by `scripts/benchmark.py extractors`.

The labelled pages of [`benchmark.md`](benchmark.md), extracted by each tool and passed
to `harfix check` and `harfix repair` with one form feed between pages. Labels say
whether the PDF's text layer is broken and do not depend on the extractor. A broken
page is caught when it is routed to `ocr`, or to `repair` and the repaired text then
labels clean; a clean page is wrongly flagged when it is routed to `ocr`. `reextract`
means the extractor damaged text that is right in the PDF; it is counted separately.
docling-parse text is each page's visible text cells, one per line, as Docling
receives it.

| Split | Extractor | Broken: ocr | Broken: repaired | Broken: reextract | Broken: missed | Clean: ocr | Clean: reextract | Clean: kept or repaired | Precision | Recall |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| test | pdfminer.six | 479 | 1 | 8 | 0 | 6 | 33 | 152 | 98.8% | 98.4% |
| all | pdfminer.six | 1110 | 4 | 40 | 6 | 6 | 47 | 366 | 99.5% | 96.0% |
| test | pdftotext | 469 | 2 | 9 | 8 | 4 | 23 | 164 | 99.2% | 96.5% |
| all | pdftotext | 1074 | 8 | 51 | 27 | 7 | 23 | 389 | 99.4% | 93.3% |
| test | docling-parse | 351 | 114 | 5 | 18 | 4 | 5 | 182 | 99.1% | 95.3% |
| all | docling-parse | 811 | 291 | 20 | 38 | 6 | 5 | 408 | 99.5% | 95.0% |

Reasons on caught broken pages (all books):

- pdfminer.six: `unmapped_glyphs` 828, `legacy_encoding` 531, `same_script_substitution` 113, `visual_order` 74, `quran_glyph_codes` 62, `lam_alef_transposition` 47, `presentation_forms` 45, `lost_word_boundaries` 8, `unmapped_elongation` 4
- pdftotext: `legacy_encoding` 896, `bidi_controls` 236, `same_script_substitution` 99, `quran_glyph_codes` 60, `unmapped_glyphs` 44, `presentation_forms` 43, `lam_alef_transposition` 12, `lost_word_boundaries` 8
- docling-parse: `unmapped_glyphs` 552, `glyph_names` 290, `legacy_encoding` 134, `same_script_substitution` 90, `presentation_forms` 71, `quran_glyph_codes` 62, `lost_word_boundaries` 37, `lam_alef_transposition` 1

Missed broken pages by reasons found (all books):

- pdfminer.six: visual_order 3, insufficient_arabic_text 2, presentation_forms, visual_order 1
- pdftotext: insufficient_arabic_text 19, bidi_controls 7, bidi_controls, presentation_forms 1
- docling-parse: none 18, insufficient_arabic_text 15, glyph_names 5
