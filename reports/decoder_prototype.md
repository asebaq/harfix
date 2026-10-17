# Font decoder prototype: pre-Unicode `AXt` / `Adv` fonts

Generated 2026-10-18 with `scripts/decoder_prototype.py --train 9 --test 9 10 18 1576
--lm-weight 0.6 --letter-bonus 1.5`.

**Decision: go.** A glyph-to-letter map learned from 80 pages of one book, with no OCR,
reads three other books set in the same font family about as well as or better than
archive.org's OCR of the same pages.

## What was tested

Four Shamela-linked books typeset in the pre-Unicode `AXt…` / `Adv…` desktop-publishing
fonts. Their PDF text layers extract as Latin gibberish (`vvvvJp`, `-!/!1-!/`), so harfix
routes every page to `ocr`.

- **Training:** half of the pages of book 9, paired with Shamela's typed text of the same
  printed pages (found through the page numbers drawn on each page).
- **Model:** each glyph is a symbol (font family plus the character it extracts as). EM
  over a monotone alignment learns, per symbol, the probability of producing nothing
  (diacritics, elongation strokes), one letter, or a two-letter ligature. Decoding
  combines those probabilities with harfix's letter model in a beam search.
- **Tuning:** the letter model's weight and per-letter bonus were chosen on book 9's
  held-out pages only.
- **Scoring:** word precision and recall of the decoded page against Shamela's typed text
  of the same page, as multisets of words.
- **Baseline:** archive.org's OCR (Tesseract) of the same PDF pages, scored the same way.

## Results

| Book | Pages | Decoder precision / recall | archive.org OCR precision / recall |
|---|---:|---:|---:|
| 9, held-out pages of the training book | 79 | 87.4% / 85.3% | 55.9% / 43.8% |
| 10, unseen book | 186 | 87.0% / 84.6% | 81.5% / 78.2% |
| 18, unseen book | 54 | 69.9% / 72.1% | 72.9% / 69.3% |
| 1576, unseen book | 191 | 80.3% / 73.2% | 67.9% / 63.6% |

Decoded without the letter model (each symbol's most likely output alone), the same
books score 7-23 points lower.

## Errors that remain

- Some lam glyphs are learned as producing nothing (`بس` for `لبس`, `ماها` for `مالها`).
- A final alef sometimes gains a lam (`قصدال` for `قصدا`).
- Quran quotations set in a separate verse font are missing from the decoded text.
- Words split at gaps after letters that do not join are handled by a rule that joins a
  lone `ال` to the next word.

## Caveats

- One font family and one publisher style. Other legacy families (`MCS…` Quran fonts,
  `Hesham…`) were not tried.
- Samples of books 10 and 18 had been looked at while building the glyph reader and the
  `ال` rule; book 1576 had not been looked at before its result.
- archive.org's OCR is Tesseract on page images. A modern vision-language OCR was not
  run and would likely do better than this baseline.
- The page offset of unseen books is found by matching decoded text to the typed pages;
  this uses the typed text for scoring only, never for decoding.

## Next

1. Train on more books of the family and on other legacy families; key each learned map
   by font family so that one map serves every book that uses it.
2. Add the verse fonts, so Quran quotations are decoded too.
3. Compare against a modern OCR model on the same pages.
4. If those hold, ship the learned maps with harfix as `harfix decode`.
