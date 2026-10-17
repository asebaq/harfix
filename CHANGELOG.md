# Changelog

## 0.1.0

First release.

- `harfix scan` audits a PDF's text layer per page and per font and routes each page to
  `keep`, `repair`, `reextract` or `ocr`.
- `harfix check` and `assess_document` judge extractor output page by page (form feeds) or
  in runs of lines, so a few bad pages are not averaged away by clean ones.
- Detects wrong glyph-to-letter maps, unmapped glyphs, presentation forms, mirrored and
  mixed reading order, lam-alef transposition and lost word boundaries.
- Detects pre-Unicode Arabic fonts whose text layer extracts as ASCII gibberish (`AXt…`,
  `Adv…` desktop-publishing fonts), not only those landing on Latin-1 symbols.
- Detects Quran glyph-ID fonts (`QCF_P…`) as `quran_glyph_codes` and never sends them to
  `repair`, where NFKC would turn them into wrong words.
- Fonts too short to judge on any single page are judged on their short runs pooled across
  the document (`"scope": "document"`).
- Fonts are identified by their full PDF name including the subset tag, so two subsets of
  one typeface with different glyph maps are reported separately.
