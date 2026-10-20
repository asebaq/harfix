# Font decoder

Generated 2026-10-20. `harfix decode` reads two kinds of font that have no usable Unicode
map:

- **Pre-Unicode `AXt…` / `Adv…` fonts**, decoded with a font map learned from typed
  editions (`scripts/train_font_maps.py`).
- **Fonts whose glyphs carry Arabic names** in the PDF's font encoding (`qafisolated`,
  `lamwithalef`, here mostly `SimplifiedArabic` subsets): the names spell the letters, so
  no map is learned.

On a decoded page, text in other fonts (Unicode headings, page numbers) is kept as it is,
unless harfix's own check rejects that font. A page's decoded text is written out only when
harfix's check routes it `keep` or `repair` ("trusted").

## Learned maps: seven `AXt` / `Adv` books

Command: for each book, `scripts/train_font_maps.py --train <the other six> --test <book>`.
The packaged map is then trained on all seven:
`--train 9 10 18 19 1291 1575 1576 --save src/harfix/data/font_maps.json.gz`.

- **Training pages:** each PDF page paired with Shamela's typed text of the same printed
  page, through the page numbers drawn on it. After a first fit, each training book is
  re-paired with the shift (within three pages) whose typed text the map reads best, and
  the map is refitted. Books 1575 and 1576 move by one page: their page numbers had been
  read one page off, so 0.3.0's map had learned from 360 pages paired with the next page's
  text.
- **Model:** each glyph is a symbol (font family plus the character it extracts as). EM
  over a monotone alignment learns, per symbol, the probability of producing nothing
  (diacritics, elongation strokes), one letter, or a two-letter ligature. The map keeps
  the four most likely outputs of each symbol seen at least three times, for families
  whose glyphs are not Arabic characters and of which at least 30% decode to letters.
- **Decoding:** as shipped (`screen_kept_fonts`, then `decode_line`): a beam search over
  the map's outputs scored with harfix's letter model (weight 0.6, per-letter bonus 1.5,
  chosen on held-out pages of book 9 in the prototype).
- **Scoring:** word precision and recall of each decoded page against the typed text of
  the same page, words of at least two letters as multisets. A test book's pages are lined
  up with its typed pages by decoded-text overlap (shifts -40..40 and the page-number
  shift); the typed text is used for scoring only.
- **Baseline:** archive.org's OCR (Tesseract) of the same PDF pages, scored the same way.

| Left-out book | Pages | Map only, precision / recall | `harfix decode`, precision / recall | archive.org OCR, precision / recall |
|---|---:|---:|---:|---:|
| 9 | 159 | 79.5% / 74.1% | 84.0% / 82.7% | 54.8% / 42.2% |
| 10 | 186 | 72.3% / 61.2% | 84.6% / 81.9% | 81.5% / 78.2% |
| 18 | 54 | 64.3% / 59.9% | 80.4% / 75.9% | 72.9% / 69.3% |
| 19 | 183 | 68.9% / 62.4% | 79.5% / 77.7% | not downloaded |
| 1291 | 69 | 42.6% / 2.3% | 62.8% / 3.2% | not downloaded |
| 1575 | 169 | 76.2% / 69.4% | 84.5% / 78.0% | 61.6% / 54.5% |
| 1576 | 191 | 71.6% / 64.9% | 78.5% / 71.8% | 67.9% / 63.6% |

"Map only" takes each symbol's most likely output; the letter model adds 4-16 points.
`harfix decode` is above archive.org's OCR on all five books with OCR to compare. Left
out, book 1291 does not decode (3% recall), although it shares font families with books
18 and 19 and decodes well once it is trained on; why was not investigated. The check
rejects 67 of its 69 pages.

The re-pairing matters: trained without it, the same leave-one-out maps scored 64.6%
(book 18), 79.3% (1575) and 73.1% (1576) precision.

### The self-check

Pages `harfix decode` trusts, against those it rejects, on the left-out books:

| Left-out book | Trusted pages | Precision of trusted | Rejected pages | Precision of rejected |
|---|---:|---:|---:|---:|
| 9 | 155 | 85.7% | 4 | 20.3% |
| 10 | 184 | 84.6% | 2 | 87.5% |
| 18 | 46 | 79.6% | 8 | 85.1% |
| 19 | 178 | 81.0% | 5 | 27.2% |
| 1291 | 2 | 43.1% | 67 | 63.4% |
| 1575 | 169 | 84.5% | 0 | — |
| 1576 | 191 | 78.5% | 0 | — |

The check catches a book that does not decode (1291) and most badly decoded pages of
books that do, but it is not a per-page accuracy guarantee: it passes text whose letters
read as Arabic, and decoded text with a fifth of its words wrong still does. On books 10
and 18 the rejected pages were as accurate as the trusted ones. Scoring lines up each
book's pages by one shift, so a page can be scored against the wrong typed page; the
lowest-scoring trusted pages (down to 0.5% on book 1576) were not inspected.

## Named glyphs: five journal-style books

Books 820, 909, 937, 944 and 946 are set in fonts without a Unicode map whose encoding
names every glyph (`/Differences [1 /space /yehfinal /fehinitial …]`). pdfminer extracts
these glyphs as `(cid:N)` or as the base encoding's Latin characters (a named `aleffinal`
on code 32 comes out as a space), so `scan` routes the pages to `ocr`. `decode` reads the
code of each glyph, spells its name, and orders the page right to left.

## Coverage of the benchmark

Command: `scripts/benchmark.py decode`. All labelled pages of the benchmark
([`benchmark.md`](benchmark.md)), decoded with the packaged map. A decoded page labels
clean when at least 75% of its words occur in Shamela's transcriptions (the benchmark's own
rule); books 9, 10, 18 and 1576 are training books of the packaged map, so their rows are
not held out.

| Page label | Decoded and trusted | Of which clean after decoding | Decoded, not trusted | Not decoded |
|---|---:|---:|---:|---:|
| broken | 310 | 310 | 0 | 850 |
| clean | 0 | 0 | 0 | 419 |

| Book | Fonts | Decoded and trusted pages | Median share of words found |
|---|---|---:|---:|
| 9 | learned map | 37 | 95.5% |
| 10 | learned map | 35 | 93.6% |
| 18 | learned map | 26 | 93.6% |
| 1576 | learned map | 36 | 95.5% |
| 820 | named glyphs | 39 | 96.0% |
| 909 | named glyphs | 37 | 95.1% |
| 937 | named glyphs | 37 | 95.2% |
| 944 | named glyphs | 26 | 94.4% |
| 946 | named glyphs | 37 | 94.1% |

So `decode` reads 27% of the benchmark's broken pages and none of its clean ones. The
share of words found is looser than word precision: a decoded word counts when it occurs
anywhere in the transcriptions. Decoding a 204-page book takes about 9 s.

## Not decoded yet

- **Verse and ornament font `Adv.QAL603`.** EM learns "produces nothing" for all its
  glyphs, so verse text set in it is missing from the output. Its few, very frequent
  glyphs look like brackets, honorifics and whole-word ligatures.
- **`HeshamNormal`, `MCSTaybahS_Unormal`.** Their glyphs carry Latin names (`eacute`,
  `Idieresis`): pre-Unicode fonts like `AXt`, but with stable names, so a map keyed by
  glyph name could be learned once for every PDF that embeds them.
- **`LotusLinotype` with names like `wawF`, `lamI`, `alifhamAU`.** Another naming scheme
  (letter plus F/I/M/U for the positional form); the name parser does not know it yet.

## Errors that remain

- Some lam glyphs are learned as producing nothing (`بس` for `لبس`).
- A final alef sometimes gains a lam (`قصدال` for `قصدا`).
- Short runs of a legacy font no map knows can come through as Latin characters (`9 GG`).

## Caveats

- One learned font family and one publisher style; seven books.
- Samples of books 10 and 18 were looked at while building the glyph reader.
- A modern vision-language OCR was not run and would likely beat the Tesseract baseline.
