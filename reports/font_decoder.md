# Font decoder: pre-Unicode `AXt` / `Adv` fonts

Generated 2026-10-18 with `scripts/train_font_maps.py --train 9 10 19 1291 --test 18 1575
1576`. The packaged map (`src/harfix/data/font_maps.json.gz`) was then trained on all seven
books with `--train 9 10 18 19 1291 1575 1576 --save …`; the numbers below come from the
four-book map, on books it never saw.

## What was tested

Seven Shamela-linked books typeset in the pre-Unicode `AXt…` / `Adv…` desktop-publishing
fonts (`Adv_FloraLa`, `Font158`, `Font159`, …), found by scanning both Shamela samples
(118 and 57 text-layer PDFs) for `legacy_encoding` fonts. Their text layers extract as
Latin gibberish (`vvvvJp`, `-!/!1-!/`), so harfix routes every page to `ocr`.

- **Training:** 597 pages of books 9, 10, 19 and 1291, each paired with Shamela's typed
  text of the same printed page (found through the page numbers drawn on the page).
- **Model:** each glyph is a symbol (font family plus the character it extracts as). EM
  over a monotone alignment learns, per symbol, the probability of producing nothing
  (diacritics, elongation strokes), one letter, or a two-letter ligature. The exported map
  keeps the four most likely outputs of each symbol seen at least three times, for font
  families whose glyphs are not Arabic characters and of which at least 30% decode to
  Arabic letters (Unicode and Latin fonts on the same pages are left out).
- **Decoding:** `harfix decode` itself (`harfix.decode.decode_line`): a beam search over
  the map's outputs scored with harfix's letter model. Its two settings (letter-model weight
  0.6, per-letter bonus 1.5) were chosen on held-out pages of book 9 in the prototype.
- **Scoring:** word precision and recall of the decoded page against Shamela's typed text
  of the same page, as multisets of words of at least two letters. An unseen book's pages
  are lined up with its typed pages by the decoded text (offsets -40..40); the typed text
  is used for scoring only.
- **Baseline:** archive.org's OCR (Tesseract) of the same PDF pages, scored the same way.

## Results

| Book | Pages | Glyphs in map | Map only, precision / recall | `harfix decode`, precision / recall | archive.org OCR, precision / recall |
|---|---:|---:|---:|---:|---:|
| 18 | 54 | 86% | 64.0% / 59.0% | 76.9% / 71.9% | 72.9% / 69.3% |
| 1575 | 169 | 97% | 74.6% / 67.8% | 84.0% / 77.4% | 61.6% / 54.5% |
| 1576 | 191 | 96% | 70.7% / 64.4% | 77.4% / 70.7% | 67.9% / 63.6% |

"Map only" takes each symbol's most likely output; the letter model adds 7-13 points.
On all three unseen books `harfix decode` scores above archive.org's OCR.

## Families that do not decode yet

- **Verse and ornament font `Adv.QAL603`.** EM learns "produces nothing" for every one of
  its glyphs, so it is not in the map; verse text set in it is missing from the output.
  Its few, very frequent glyphs look like brackets, honorifics and whole-word ligatures
  rather than letters; they need multi-letter outputs.
- **`HeshamNormal` / `SimplifiedArabic` / `MCSTaybahS_Unormal` (seven journal-style
  books).** Their glyphs extract as raw glyph IDs (`(cid:10)`), which each PDF's font
  subset numbers differently, so a map learned on one book does not carry over to another.
  These need glyph-shape fingerprints from the embedded font programs instead of codes.
  Their printed page numbers were not read reliably either (offsets such as 77 and -777
  came out), so their training pages were mispaired.

## Errors that remain

- Some lam glyphs are learned as producing nothing (`بس` for `لبس`).
- A final alef sometimes gains a lam (`قصدال` for `قصدا`).
- Some word endings are lost (`إثبا` for `إثبات`).

## Caveats

- One font family and one publisher style; seven books.
- Samples of books 10 and 18 were looked at while building the glyph reader; book 18 is
  scored here, books 1575 and 1576 had not been looked at.
- A modern vision-language OCR was not run and would likely beat this Tesseract baseline.
- `harfix decode` decodes a page only when the map knows at least 80% of its glyphs, and
  trusts the result only when harfix's own check routes it `keep` or `repair`.
