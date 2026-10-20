# harfix repair: Shamela books

Generated 2026-10-20 by `scripts/benchmark.py repair`.

Each PDF's first pages are extracted, passed through `repair_text`, and every page it
changed is scored before and after: the share of its Arabic words (diacritics and
tatweel removed, nothing else normalized, as a plain search index would see them)
that occur in Shamela's typed transcriptions. A page is worse when that share drops
by more than a point without more words found (spelling out glyph names adds words
that the share before did not count).

| Extractor | Pages repaired | Reasons | Median share before | Median share after | Pages worse |
|---|---:|---|---:|---:|---:|
| pdfminer.six | 453 | `visual_order` 453, `presentation_forms` 22 | 20.0% | 90.4% | 0 |
| pdftotext | 562 | `bidi_controls` 562, `presentation_forms` 87, `unmapped_elongation` 13 | 25.4% | 92.0% | 0 |
| docling-parse | 141 | `glyph_names` 174, `presentation_forms` 94, `unmapped_elongation` 14 | 6.1% | 97.1% | 0 |
