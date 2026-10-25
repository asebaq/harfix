# Changelog

## Unreleased

- `check` reports words run together (`merged_words`, route `reextract`): more than 15%
  of the letters in tokens of 12 letters or more. Not seen in typed Arabic or in the
  output of pdfminer.six, pdftotext or docling-parse on the benchmark; it stops `decode`
  from trusting pages whose word gaps it could not rebuild.
- `decode` takes the PDF's own space glyphs as word gaps, however narrow, in fonts that
  read as Arabic or are named. Mean share of words found per page: book 30628 89.8% →
  96.4%, 926 88.5% → 90.3%, 1258 91.2% → 92.8%; the learned-map books are unchanged.
  With both changes, on the benchmark's broken pages (Quran table built), `decode` trusts
  455 pages that label clean (452 before) and 4 that still have a quarter of their words
  wrong (9 before).

## 0.6.0

- The packaged font map reads Quran quotations in the `AXt` / `Adv` books: their
  one-glyph-per-word `Advzy…` subsets are learned word by word from the typed quotations
  (1500 glyphs). On books 1575 and 1576, 64-74% of the quoted words come out (16-17%
  before); on a book held out of training, 20-28%. `scripts/train_font_maps.py` learns them.
- The packaged map reads `HeshamNormal`, a pre-Unicode heading font of six journal
  issues in the corpus, keyed by its glyph names so it holds across subsets and PDFs.
  On a held-out book, 64-89% of the heading words come out right; page recall rises
  1-2.5 points, precision moves -0.8 to +0.1.
- `decode` reads each glyph of fake-bold text once (glyphs drawn several times a
  fraction of a point apart), and reads `c128`-style glyph names by their original code
  instead of the subset's.
- `scripts/train_font_maps.py` pairs PDF pages with the typed text by their text before
  their page numbers, feeds named glyphs to EM as their letters, and gains `--families`
  and `--add-to`.

## 0.5.0

- `decode` reads two more glyph-naming schemes: Linotype Lotus style (`lamI`,
  `alifhamAU`, `tamarF`, `oneA`) and form-first (`fnalef`, `midmeem`), plus marks,
  elongation and the fonts' own sign names. Names now win over a font's Unicode map, which
  in these books is partial or wrong. On the benchmark, `decode` reads 417 broken pages,
  up from 310 (`reports/font_decoder.md`); it still decodes no clean page.
- `check` and `repair` read the same schemes when docling-parse glues them into the text
  (`tamarFbaIalifF`): 291 broken docling-parse pages are now repaired instead of sent to
  OCR, at 95.0% recall and 99.5% precision.
- Quran page fonts (`QCF_Pnnn`, `QCF2nnn`) decode word by word with a table built by
  `scripts/build_quran_glyphs.py`. The table is not shipped yet: permission to
  redistribute the glyph codes has been asked (TarteelAI/quranic-universal-library#909).
  A page with at least five glyphs read exactly (named or Quran glyphs) is decoded even
  when most of its text is in other, readable fonts.
- `FontMap.coverage` also returns how many glyphs are read exactly;
  `FontMap.wants_decoding` says whether a page has glyphs to decode.

## 0.4.0

- `check` and `repair` read the output of extractors that write unmapped glyphs other
  than as `(cid:N)`, such as docling-parse (Docling's PDF parser):
  - new reason `glyph_names` (route `repair`): Arabic glyph names written as text
    (`yehfinalfehinitial`); `repair` spells them out in reading order;
  - glyph codes written as decimal numbers are `unmapped_glyphs`;
  - a pre-Unicode font written one character per text cell is `legacy_encoding`.
  On docling-parse text of the Shamela benchmark, recall rose from 33.5% to 95.2% at
  99.5% precision; pdfminer.six and pdftotext are unchanged (`reports/extractors.md`).
- `harfix decode` also decodes fonts without a Unicode map whose glyphs carry Arabic
  names in the PDF's font encoding: exact, no font map needed. Text in other fonts on a
  decoded page (Unicode headings, page numbers) is kept, unless harfix's own check
  rejects that font. `DecodedPage` gains `decoded_share`.
- `scan` marks fonts and pages `harfix decode` can read (`"decodable": true`) and says so.
- Font maps: training re-pairs pages whose printed page numbers were misread by a page;
  two of the seven books had been trained on pages paired with their neighbours' text.
  The packaged map is retrained: left-out books now decode at 78-85% word precision.
- `scripts/benchmark.py extractors` and `decode`: `check` on three extractors, and
  `decode` on the labelled pages.
- Fixed: `decode_pdf(pages=[])` decoded every page.

## 0.3.0

- `harfix decode` and `decode_pdf()`: decode pre-Unicode Arabic fonts without OCR, with a
  packaged font map for the `AXt…` / `Adv…` desktop-publishing family learned from seven
  books and their typed editions. A page is decoded only when the map knows at least 80%
  of its glyphs, and its text is kept only when harfix's own check routes it `keep` or
  `repair`. On three books the map never saw, 77-84% of decoded words are right, above
  archive.org's OCR of the same pages (62-73%); see `reports/font_decoder.md`.
- `scripts/train_font_maps.py` learns and evaluates font maps (needs the `decoder` group).

## 0.2.0

- `harfix repair` and `repair_text()`: apply the safe fixes to pages `check` routes to
  `repair` (delete bidi marks and unmapped elongation glyphs, turn visual-order lines into
  logical order with numbers, Latin words and brackets kept right, decompose presentation
  forms), log every change, and list pages that still need `reextract` or `ocr`.
- New reason `bidi_controls` (route `repair`): bidi embedding marks, which pdftotext
  inserts on about half of its Arabic pages and which stick to the neighbouring words.
- `scripts/benchmark.py repair` and `reports/repair.md`: on Shamela PDFs, the share of
  words a plain search index matches rose from 20% to 90% (pdfminer.six) and from 25% to
  92% (pdftotext) on the pages repaired, with no page worse.

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
