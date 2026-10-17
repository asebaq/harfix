# harfix repair: Shamela books

Generated 2026-10-18 by `scripts/benchmark.py repair`.

Each PDF's first pages are extracted, passed through `repair_text`, and every page it
changed is scored before and after: the share of its Arabic words (diacritics and
tatweel removed, nothing else normalized, as a plain search index would see them)
that occur in Shamela's typed transcriptions.

| Extractor | Pages repaired | Reasons | Median share before | Median share after | Pages worse |
|---|---:|---|---:|---:|---:|
| pdfminer.six | 453 | `visual_order` 453, `presentation_forms` 22 | 20.0% | 90.3% | 0 |
| pdftotext | 562 | `bidi_controls` 562, `presentation_forms` 87, `unmapped_elongation` 13 | 25.4% | 92.0% | 0 |
