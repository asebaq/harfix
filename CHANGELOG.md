# Changelog

## 0.1.1

- New reason `unmapped_elongation` (route `repair`): U+FFFD only inside words that read
  correctly without it, as when elongation (kashida) glyphs have no Unicode mapping.
  Such text was sent to `ocr` before.
- `legacy_encoding` also catches pre-Unicode fonts mapped onto ASCII digits and
  punctuation (`0)#`, `-!/!1-!/`), not only onto letters or Latin-1 symbols.
- Fixed: ornate parentheses ﴾﴿ around Quran quotations were counted as presentation forms,
  so pages quoting many verses could be flagged `quran_glyph_codes`. Only characters that
  NFKC decomposes into letters now count as presentation forms.
- Real-book benchmark (`scripts/benchmark.py`, `reports/benchmark.md`): 57 PDFs linked
  from al-Maktaba al-Shamela, labelled from Shamela's typed transcriptions, split into
  dev and test books.
- README: logo and badges.

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
