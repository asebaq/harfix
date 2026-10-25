# Font decoder

Generated 2026-10-21. `harfix decode` reads three kinds of font that have no usable
Unicode map:

- **Pre-Unicode `AXt…` / `Adv…` fonts**, decoded with a font map learned from typed
  editions (`scripts/train_font_maps.py`).
- **Fonts whose glyphs carry Arabic names** in the PDF's font encoding (`qafisolated`,
  `lamI`, `fnalef`): the names spell the letters, so no map is learned.
- **Quran page fonts** (`QCF_P063`): each glyph is a word of a known Mushaf page, read from
  a table that is not shipped yet (see below).

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

## Named glyphs

Fonts whose encoding names their glyphs (`/Differences [1 /space /yehfinal /fehinitial …]`)
are read through the names. pdfminer extracts such glyphs as `(cid:N)` or as the base
encoding's Latin characters (a named `aleffinal` on code 32 comes out as a space), so
`scan` routes the pages to `ocr`; `decode` reads each glyph's code, spells its name, and
orders the page right to left. Three naming schemes are known:

| Scheme | Examples | Books |
|---|---|---|
| Adobe-style, form as a word | `qafisolated`, `lamwithaleffinal`, `allahisolated` | 820, 909, 937, 944, 946 |
| Linotype Lotus, form as a capital | `lamI`, `alifhamAU`, `lamalihamBF`, `tamarF`, `oneA` | 192, 926, 1258, 30628 |
| Form as a prefix | `fnalef`, `inbaa`, `midmeem`, `fnhamzahonwaw` | 192, 820 |

Where a font also has a Unicode map, the names win: in these books the maps are partial
(glyphs extract as `(cid:N)`) or wrong. Two Lotus names were ambiguous and were settled
against the typed text: `pa` is ط and `ta` is ت (the other way round, the median share of
words found falls by 8-11 points on books 926, 30628 and 192). Marks (`fathaA`),
elongation (`kashidashort`) and the font's own sign names (`openparen`, `fullpoint`) are
read too.

Median share of decoded words found in Shamela's transcriptions, on 25 sample pages each:

| Book | Scheme | Decoded pages | Trusted | Median share of words found |
|---|---|---:|---:|---:|
| 820 | Adobe-style, prefix | 25 | 25 | 97.3% |
| 926 | Lotus | 24 | 24 | 92.7% |
| 30628 | Lotus | 25 | 23 | 94.5% |
| 192 | Lotus, prefix | 24 | 22 | 91.1% |

docling-parse writes these names into the text itself, glued per word
(`yehfinalfehinitial`, `tamarFbaIalifF`); `check` and `repair` read all three schemes there
too (see [`extractors.md`](extractors.md)).

## Quran page fonts

The King Fahd Complex page fonts of the Madinah Mushaf (`QCF_P001`…`QCF_P604` for the
1405H print, `QCF2001`… for the 1421H print) draw one glyph per word of that page.
`scripts/build_quran_glyphs.py` builds a table of every word's page and glyph codes in
both prints from the Quran.com API, and `decode` reads each glyph as its word, without
diacritics. PDFs write the glyphs on Presentation Forms-A code points or on byte codes
from 0x21; both are read. In the first 60 pages of 69 sample PDFs with Quran fonts, 84% of
the page-font glyphs are found in the table (67% counting the basmala fonts `QCF_BSML`
and the `AQS…` fonts, which are not read).

The table is not shipped: neither Quran.com nor QUL publishes a licence for the glyph
codes, and permission to redistribute them has been asked
(TarteelAI/quranic-universal-library#909). Without it, Quran page fonts stay unread.
Built locally, it adds 40 trusted pages to the coverage below (459 broken pages, of which
455 label clean), and decodes 4 clean pages, which still label clean. 3 of the added
trusted pages do not label clean. On the 2 of them in book 30131, the body font has a
partly wrong Unicode map (`الؿال` for `المال`) that harfix's check passes, so decoding the
quotations makes a page trusted whose body is not right; the third (book 806) was not
inspected.

## Quran quotations in the learned-map books

The `AXt` / `Adv` books set each Quran quotation between two `Advzy0` brackets, in small
font subsets of their own (`Advzy251337`, `Advzy364547`, …) that draw one glyph per word;
the subsets reuse the same low codes, and only a few subset names recur between books. A
font map learns at most two letters per glyph, so EM cannot read them. `train_font_maps.py`
now learns them from the typed quotations (`﴿…﴾`) instead: on a page with as many bracketed
glyph runs as typed quotations, a run with as many glyphs as its quotation has words gives
glyph *i* word *i*, and a glyph keeps the word most of its occurrences vote for. On books
1575 and 1576 the runs and quotations match one to one (187 and 256 of each). EM's own
guesses for fonts used (≥90%) only between brackets are dropped; the packaged map has 1500
verse glyphs (13 KB → 20 KB).

Quoted words of three letters or more found in the decoded page, every fourth page:

| Book | Quoted words | Before | Book held out of training | Packaged map (book in training) | Other words, before → after |
|---|---:|---:|---:|---:|---:|
| 1575 | 401 | 17% | 28% | 74% | 85% → 85% |
| 1576 | 546 | 16% | 20% | 64% | 76% → 76% |

Most of the gain needs the book in training: few subsets recur between books, so on
another book only the shared ones are read. The count is loose (a quoted word counts if
it occurs anywhere on the decoded page). The coverage table below is unchanged: with the
local Quran table, its output is identical with the old and the new map.

## Pre-Unicode fonts with Latin glyph names: `HeshamNormal`

Six journal issues in the corpus (books 909, 929, 936, 937, 944, 946) set headings in
`HeshamNormal`, a pre-Unicode font whose Arabic glyphs sit on Latin slots (`<` is the
space, `]` alef, `Ö` lam: `]ÖË’Ø<]Ön^Þê` is الفصل الثاني). Each PDF embeds several subsets
of it, and each subset renumbers its glyphs (code 2 is `aacute` in one subset, `Eth` in
another), but the glyph names stay: pdfminer extracts them as the Latin character they
name, so a map learned on these characters holds for every PDF of the font. Names that
give only the original code (`c128`) are now read as that code (`\x80`) instead of the
subset's `(cid:N)`: in book 909 that leaves 9 unread `HeshamNormal` / `MCSTaybahS` glyphs,
against 211 before.

Training:

- Page numbers do not pair these PDFs with the typed text: the digits read give offsets
  of 34, 77 and -115 pages in books 909, 937 and 946 and none in 944, where the text
  gives 0. `train_font_maps.py` now pairs a
  PDF by its text first: each fifth page, read with the packaged map and the glyph names,
  goes with the typed page sharing most of its words, and the most common shift wins. On
  the seven `AXt` books it gives the page numbers' shift, or the one the re-pairing step
  found (+1 page for 1575 and 1576).
- Named glyphs are read exactly, but some draw more letters than EM lets a symbol emit;
  they enter EM as one symbol per letter, each starting out on its letter. Before this,
  the first fit on these books learned 3 symbols.
- Headings are often set in fake bold: each glyph drawn several times a fraction of a
  point apart (20-33% of the `HeshamNormal` glyphs in books 909, 929 and 944 are extra
  copies). `glyph_lines` now keeps one copy, for every font.
- `--families HeshamNormal MCSTaybahS_Unormal.` keeps only those fonts (EM also passes
  `AGAArabesque` and two Unicode fonts as legacy on these pages); `--add-to` adds them to
  the packaged map, whose other fonts and gaps are kept. Map size 20 KB → 21 KB.

Each book held out in turn (trained on the other four of 909, 929, 937, 944, 946):

| Book | Hesham words decoded | Found on the typed page | Page precision before → after | Page recall before → after |
|---|---:|---:|---:|---:|
| 909 | 258 | 82% | 93.4% → 92.7% | 78.5% → 81.0% |
| 929 | 153 | 89% | 91.3% → 91.4% | 81.9% → 82.8% |
| 937 | 311 | 64% | 97.8% → 97.1% | 88.8% → 89.8% |
| 944 | 364 | 70% | 93.4% → 92.6% | 76.2% → 77.4% |
| 946 | 153 | 87% | 96.6% → 96.2% | 82.6% → 83.7% |

Words of three letters or more decoded from `HeshamNormal` glyphs alone; a word counts if
it occurs on the typed page. Page scores are over all paired pages (most of their text is
in named glyphs, which decode as before). The remaining errors drop or change a letter:
`القرن` (القرآن), `التفسب` (التفسير), `السعوية` (السعودية), probably glyphs seen rarely in
the four training books. `MCSTaybahS_Unormal` is not learned (see below). On the
benchmark, only book 1258 changes (one more broken page decoded and clean), from the
overprint and `c128` changes; the Hesham books' benchmark pages were already decoded and
trusted through their named body font, and stay so.

## Word gaps

`decode` rebuilds word gaps from glyph positions, and a page whose gaps come out too
narrow runs its words together (`الخدريرضياللهعنهأنهكانيفعلذلك`). harfix's check passed
such pages: the letters read as Arabic.

- **Space glyphs.** Many PDFs draw a space glyph between words, sometimes narrower than
  the gap `decode` reads as a space. `glyph_lines` now cuts a word wherever a space
  glyph's centre falls in the gap between two glyphs (not over a glyph: some PDFs draw a
  word's trailing space over its last letter), for fonts whose glyphs read as Arabic
  letters or are named. A pre-Unicode font may draw a letter on the space's code: taking
  the AXt books' spaces as gaps turned `الواجب` into `الوالجب`.
- **Check.** A new reason, `merged_words` (route `reextract`): more than 15% of the
  letters in tokens of 12 letters or more, in an extractor's output or in decoded text
  (not in a raw text-layer scan). Typed Arabic stays under 7% (377 calibration pages),
  and pdfminer.six, pdftotext and docling-parse under 3% (514 kept pages of the dev
  split); `scripts/benchmark.py extractors` gives the same table with and without the rule.
  On the synthetic test windows, clean text is flagged as often as before (1.2%, 1.8%,
  4.2% at 80, 200, 500 letters), and text with half its spaces dropped is reported as
  `merged_words` in 84%, 80% and 91% of windows (89%, 98%, 100% flagged at all).

Space glyphs, on whole books (share of each page's words found in Shamela's
transcriptions, mean over decoded pages):

| Book | Fonts | Pages | Before | After | Pages better / worse by > 2 points |
|---|---|---:|---:|---:|---:|
| 30628 | named glyphs | 289 | 89.8% | 96.4% | 165 / 1 |
| 926 | named glyphs | 626 | 88.5% | 90.3% | 284 / 29 |
| 1258 | named glyphs | 222 | 91.2% | 92.8% | 88 / 11 |
| 820 | named glyphs | 145 | 95.6% | 96.5% | 23 / 8 |
| 909, 929, 937, 944, 946 | named glyphs, Hesham | 609 | 93.0-94.1% | ±0.3 points | 1 / 0 |
| 9, 10, 18, 19, 1291, 1575, 1576 | learned map | 1,021 | | identical text | |

In book 926 the worse pages gain stray punctuation from a font with a wrong map
(`loutsshamy`) that the book-wide screening of kept fonts no longer rejects
(`وعشري*ن *سن*ة`).

On the benchmark's broken pages, with the Quran table built:

| `decode` | Trusted, label clean | Trusted, label not clean | Not trusted |
|---|---:|---:|---:|
| 0.6.0 | 452 | 9 | 6 |
| + space glyphs | 463 | 5 | 5 |
| + `merged_words` | 455 | 4 | 14 |

The check untrusts 9 pages (8 in the dev split, 1 in the test split). The benchmark's
rule, which counts words, labels 8 of them clean; counted by letters, 8 of the 9 have
less than 75% of their letters in words found (40-73%), since the run-together tokens are
long (`إخوانهالمسلمينبالألفاظالحسنةوأسمائهمالتي`). 7 are in book 815, whose `LotusLinotype`
draws no space glyphs between words. Without the Quran table, 417 → 418 trusted pages
label clean and 1 does not (was 1).

## Coverage of the benchmark

Command: `scripts/benchmark.py decode`. All labelled pages of the benchmark
([`benchmark.md`](benchmark.md)), decoded with the packaged map and without the Quran
table. A decoded page labels clean when at least 75% of its words occur in Shamela's
transcriptions (the benchmark's own rule); books 9, 10, 18 and 1576 are training books of
the packaged map, so their rows are not held out.

| Page label | Decoded and trusted | Of which clean after decoding | Decoded, not trusted | Not decoded |
|---|---:|---:|---:|---:|
| broken | 419 | 418 | 5 | 733 |
| clean | 0 | 0 | 0 | 420 |

| Book | Fonts | Decoded and trusted pages | Clean after decoding |
|---|---|---:|---:|
| 9 | learned map | 37 | 37 |
| 10 | learned map | 35 | 35 |
| 18 | learned map | 26 | 26 |
| 1576 | learned map | 36 | 36 |
| 820 | named glyphs | 38 | 38 |
| 909 | named glyphs | 37 | 37 |
| 926 | named glyphs | 36 | 36 |
| 937 | named glyphs | 37 | 37 |
| 944 | named glyphs | 26 | 26 |
| 946 | named glyphs | 36 | 36 |
| 1258 | named glyphs | 36 | 36 |
| 30628 | named glyphs | 39 | 38 |

So `decode` reads 36% of the benchmark's broken pages (27% in 0.4.0) and none of its clean
ones. The share of words found is looser than word precision: a decoded word counts when
it occurs anywhere in the transcriptions. Decoding a 204-page book takes about 9 s.

## What is left

Of the broken benchmark pages `scan` sends to `ocr` as `same_script_substitution` (letters
present but not reading as Arabic), split by font run:

| Cause | Font-pages | Books | Fonts |
|---|---:|---:|---|
| Letters swapped by a wrong Unicode map | 136 | 12 | LotusLinotype, TraditionalArabic, mylotus |
| Letters scattered, many missing | 74 | 5 | loutsshamy, adwa-assalaf |
| Letters right, word spacing broken | 53 | 10 | KFGQPCUthmanTahaNaskh, adwa-assalaf |

The first could be solved per book as a substitution cipher with the letter model; the
second needs the glyphs themselves (codes or outlines), since the text has lost letters;
the third is an extraction fault that another extractor may not have.

Fonts not decoded yet:

- **Quran quotations in `AXt` / `Adv` books outside training.** Their verse subsets are
  mostly not shared between books (see above): 20-28% of the quoted words come out on a
  held-out book. `Adv.QAL603` and `Font575` / `Font445`, which EM learns as producing
  nothing, are ornaments and running heads (book title, chapter, page number) that the
  typed editions leave out; they are dropped.
- **`MCSTaybahS_Unormal`.** EM learns no letters for it from the typed editions; the
  lines of it looked at are page heads (journal name, issue), which the typed editions
  leave out.
- **Fonts with neither names nor a Unicode map** (`AL-Mohanad`, `AGAArabesque`, fonts
  pdfminer cannot name): only their codes are left.

## Errors that remain

- Some lam glyphs are learned as producing nothing (`بس` for `لبس`).
- A final alef sometimes gains a lam (`قصدال` for `قصدا`).
- Short runs of a legacy font no map knows can come through as Latin characters (`9 GG`).

## Caveats

- One learned font family and one publisher style; seven books.
- Samples of books 10 and 18 were looked at while building the glyph reader.
- A modern vision-language OCR was not run and would likely beat the Tesseract baseline.
