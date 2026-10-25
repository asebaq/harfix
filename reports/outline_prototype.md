# Glyph-outline prototype: fonts with a wrong Unicode map

Generated 2026-10-25 with `scripts/outline_prototype.py`.

**Decision: no-go** as a `decode` feature for now. Reading glyphs by their outlines fixes
the letters of fonts that recur in the corpus and leaves clean text alone, but on the
benchmark it makes 8 more broken pages clean while 46 more pages pass harfix's check with
a quarter or more of their words still wrong.

## What was tested

The cipher prototype ([`cipher_prototype.md`](cipher_prototype.md)) found that a wrong
Unicode map comes with the PDF, not with the font: `mylotus` is clean in books 17773 and
800 and broken in 1477. So the glyph drawn should be identified, not the text guessed.

- **Fonts:** all 35 font runs labelled broken by wrong letters
  (`same_script_substitution`) embed a TrueType program (`FontFile2`) next to their
  ToUnicode map: 197 run-pages in Type0 fonts with an Identity CID-to-glyph map, 107 in
  simple TrueType fonts.
- **Index:** every embedded TrueType glyph in the corpus (213 PDFs, 6,822 fonts, 143,967
  glyphs): its outline, decomposed and scaled to 1000 units per em, is hashed, and its PDF
  votes for the text its ToUnicode map gives it. Glyphs without contours share one key.
- **Reading:** a glyph is read as the other PDFs read it when at least 2 of them agree
  (60% of those that have it). A book's own PDFs never vote for it.
- **Runs:** the broken runs and the clean controls of the cipher prototype, re-extracted
  with pdfminer with only the contradicted glyphs changed, scored by the share of words
  found in Shamela's transcriptions.
- **Pages:** all labelled benchmark pages through `harfix decode`, with each font whose
  map the other PDFs contradict (at least 5 glyphs and 10% of the glyphs they agree on)
  read as named glyphs, so `decode` rebuilds lines and word gaps from glyph positions.
  Both columns use the locally built Quran table, so the baseline is 452, not 417.

## Results

Outlines recur: for the median broken run, 99% of its glyphs occur in other PDFs, and the
other PDFs contradict its map on 19% of them; for clean controls, on 1%.

| Runs | Count | Median share of words found, before → after | Worse by > 2 points | At ≥ 75% (clean) |
|---|---:|---:|---:|---:|
| Broken | 30 | 27% → 34% | 1 | 1 → 2 |
| Clean (controls) | 33 | 86% → 87% | 0 | 28 → 28 |

The cipher solver reached 41% on the broken runs but made 14 of 25 controls worse; outlines
make none worse. Where the font is in the corpus the letters come back:

| Book | Font | Words | Found before → after |
|---|---|---:|---:|
| 1477 | mylotus | 886 | 31% → 76% |
| 1040 | Lotus Linotype | 453 | 32% → 73% |
| 30131 | Sultan bold | 72 | 15% → 68% |
| 30131 | PT Bold Heading | 26 | 27% → 64% |
| 1477 | mylotus,Bold | 218 | 29% → 62% |
| 23 | adwa-assalaf, adwa-assalaf,Bold | 221, 260 | 34%, 32% → 56% |
| 1124 | Lotus Linotype | 616 | 35% → 54% |

Through `decode`, on the benchmark's labelled pages:

| Page label | Outcome | `decode` as shipped | With outline readings |
|---|---|---:|---:|
| broken | trusted, labels clean | 452 | 460 |
| broken | trusted, labels partial | 9 | 53 |
| broken | trusted, labels broken | 0 | 2 |
| broken | not trusted | 6 | 70 |
| broken | not decoded | 690 | 572 |
| clean | trusted, labels clean | 4 | 5 |
| clean | not decoded | 416 | 415 |

No clean page is made worse. But the share of trusted pages that label clean falls from
98% (452 of 461) to 89% (460 of 515).

## Why it falls short

- **The letters are not the only fault.** In 1477 every glyph has votes, yet the misses
  are words read backwards with their lam-alef written the other way (`لاثملاا`, `للها`)
  and words split into single letters. In 370 `loutsshamy` (11,076 words) the outlines
  restore missing letters (`َــخ ِرا`, `َم َح َّــب ُة`) but every glyph comes out space-separated.
  In 815 `LotusLinotype` the map is right and the text is in visual order with no word
  spaces. `repair_text` changes none of these runs. Through `decode`'s layout many such
  pages improve to "partial", and harfix's check passes them.
- **Font versions not in the corpus.** In 1452 `TraditionalArabic` (7,924 words), 144 of
  270 glyphs match no other PDF; 1106 `Simplified Arabic`, 806 `Harf-Fannan` and 138
  `KFGQPCUthmanTahaNaskh` barely match either. A shipped table would know only the fonts
  of the PDFs it was built from.
- **Shipping the table** means distributing outline hashes and readings derived from
  third-party fonts and PDFs, a question of its own (as with the Quran table).

## What it would take

A page whose letters are fixed but whose words are still split or reversed must not be
trusted; until the check rejects such pages (or the layout faults are fixed first),
outline readings raise the number of wrong pages harfix trusts. Font coverage would then
grow only with the corpus the table is built from.

## Re-run with word gaps (2026-10-25)

After `decode` took the PDF's space glyphs as word gaps and the check gained
`merged_words` ([`font_decoder.md`](font_decoder.md#word-gaps)), the same command gives:

| Page label | Outcome | `decode` | With outline readings |
|---|---|---:|---:|
| broken | trusted, labels clean | 455 | 464 |
| broken | trusted, labels partial | 4 | 11 |
| broken | not trusted | 14 | 115 |
| broken | not decoded | 684 | 567 |
| clean | trusted, labels clean | 4 | 5 |

Outline readings now add 9 right pages for 7 wrong ones, against 8 for 46 before; the
share of trusted pages that label clean would fall from 99.1% to 97.7%. Still no-go. 9
of the 11 wrong pages are in book 138, where some glyphs are still read as the wrong
letter or not at all (`قَبْدُ العََزِيزِ` for عَبْدُ العَزِيزِ, `مَُم,دٌ` for مُحَمَّدٌ, a shadda
read as a comma): the check passes text with a few wrong letters per line.
