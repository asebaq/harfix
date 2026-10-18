<h1 align="center">
  <a href="https://github.com/asebaq/harfix">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/asebaq/harfix/main/docs/assets/cover_dark.svg">
      <img alt="harfix" src="https://raw.githubusercontent.com/asebaq/harfix/main/docs/assets/cover_light.svg" width="640">
    </picture>
  </a>
</h1>

<p align="center">
  <a href="https://pypi.org/project/harfix/"><img alt="PyPI" src="https://img.shields.io/pypi/v/harfix?color=0F766E"></a>
  <a href="https://pypi.org/project/harfix/"><img alt="Python" src="https://img.shields.io/python/required-version-toml?tomlFilePath=https%3A%2F%2Fraw.githubusercontent.com%2Fasebaq%2Fharfix%2Fmain%2Fpyproject.toml"></a>
  <a href="https://github.com/asebaq/harfix/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/asebaq/harfix/actions/workflows/ci.yml/badge.svg"></a>
  <a href="https://github.com/asebaq/harfix/blob/main/LICENSE"><img alt="License" src="https://img.shields.io/github/license/asebaq/harfix"></a>
</p>

<p align="center">
  <a href="#install"><strong>Install</strong></a> &middot;
  <a href="#use"><strong>Use</strong></a> &middot;
  <a href="#routes-and-reasons"><strong>Routes</strong></a> &middot;
  <a href="#how-it-works"><strong>How it works</strong></a> &middot;
  <a href="#accuracy"><strong>Accuracy</strong></a> &middot;
  <a href="#roadmap"><strong>Roadmap</strong></a>
</p>

**A quality gate for Arabic text extracted from PDFs.** harfix tells you, per page and per
font, whether the text you are about to index is trustworthy, needs a cheap repair, needs
re-extraction with a different tool, or must go to OCR.

Arabic PDFs fail silently. A page can render perfectly and still extract as the wrong
letters (`المدعى عليه` → `الددعى عليهي`), as presentation-form code points that match no
search query, as mirrored lines, or as pre-Unicode symbols (`Âd‡;« ≤∞`). Generic
"broken text" detectors check for control characters and Latin mojibake, so they pass
this text straight into your RAG index. harfix scores the letters themselves with a small
Arabic character model and reports what is wrong and what to do about it.

harfix never modifies text. It only decides.

## Install

```bash
pip install harfix        # or: uv add harfix
```

Python 3.10+. The only runtime dependency is `pdfminer.six`; the two character models
(~300 KiB) ship with the package.

## Use

Audit the text layer of PDFs:

```console
$ harfix scan --pages 8-12 --fail-on ocr mukhtasar_khuqayr.pdf
mukhtasar_khuqayr.pdf
  pages: keep=1, ocr=4
  p9     ocr       legacy_encoding
  p10    ocr       legacy_encoding
  p11    ocr       legacy_encoding
  p12    ocr       legacy_encoding
```

That book was typeset in pre-Unicode Arabic fonts (`AXt…`, `Adv…`), so its text layer
extracts as Latin gibberish. `-v` lists every font on every page; `--json` prints the full
report; `--fail-on repair|reextract|ocr` turns the scan into a CI or pipeline gate (exit
code 1).

Check text produced by any extractor (Docling, pdftotext, Marker, an OCR engine). Pages
separated by form feeds (pdftotext's default) are judged one by one; other text in runs of
whole lines holding about 500 Arabic letters, so a few bad pages are not averaged away:

```console
$ pdftotext -f 1 -l 12 al_mughalatat.pdf - | harfix check
reextract: bidi_controls, lam_alef_transposition, presentation_forms
  pages: repair=5, reextract=2
  p3               repair    bidi_controls
  p4               repair    bidi_controls, presentation_forms
  p5               repair    bidi_controls, presentation_forms
  p6               reextract bidi_controls, presentation_forms, lam_alef_transposition
  p7               repair    bidi_controls
  p9               repair    bidi_controls, presentation_forms
  p11              reextract bidi_controls, presentation_forms, lam_alef_transposition
```

Page numbers count from the start of the input; blank pages are skipped.

Repair what is safe to repair. `harfix repair` changes only the pages `check` routes to
`repair`, and only for the reasons found on them: it deletes bidi embedding marks and
unmapped elongation glyphs, turns visual-order lines into logical order (numbers and Latin
words keep their own order, brackets are mirrored), and decomposes presentation forms.
Pages that need `reextract` or `ocr` are left untouched and listed:

```console
$ pdftotext -f 1 -l 12 al_mughalatat.pdf - | harfix repair -o repaired.txt
repaired p3: bidi_controls (8 characters)
repaired p4: bidi_controls (62 characters)
repaired p4: presentation_forms (278 characters)
repaired p5: bidi_controls (172 characters)
repaired p5: presentation_forms (289 characters)
repaired p7: bidi_controls (8 characters)
repaired p9: bidi_controls (12 characters)
repaired p9: presentation_forms (66 characters)
not repaired p6: reextract (bidi_controls, presentation_forms, lam_alef_transposition)
not repaired p11: reextract (bidi_controls, presentation_forms, lam_alef_transposition)
```

Decode pre-Unicode fonts without OCR. `harfix decode` reads the glyphs of each page and
decodes them with font maps learned from typed editions of other books in the same fonts
(packaged: the `AXt…` / `Adv…` family). A page is decoded only when the map knows at least
80% of its glyphs, and its text is written out only when harfix's own check passes it
(`keep` or `repair`); other pages stay empty, so page positions are kept:

```console
$ harfix decode --pages 8-12 mukhtasar_khuqayr.pdf -o decoded.txt
not decoded p8: font map knows 0% of its glyphs
decoded p9
decoded p10
decoded p11
decoded p12
$ sed -n 3p decoded.txt
هذا المختصر أملاه الشيخ أبو بكر وير في أخر حياته بعد عام
```

Decoded text gets about 70-85% of words right, so it is meant for search and triage, not
for quoting. `--json` prints every page with its share of known glyphs and its check.

From Python:

```python
from harfix import assess_document, assess_text, decode_pdf, repair_text, scan_pdf

report = scan_pdf("book.pdf", pages=range(1, 11))
for page in report.pages:
    if page.route != "keep":
        print(page.page, page.route, page.reasons)

document = assess_document(extracted_text)  # extractor output, page by page
document.route, [(s.page, s.assessment.route) for s in document.segments]

fixed = repair_text(extracted_text)  # repaired text, a change log, unrepaired pages
fixed.text, fixed.changes, fixed.unrepaired

verdict = assess_text(snippet)  # one piece of text: checks reading order too

pages = decode_pdf("book.pdf")  # DecodedPage: text, known_share, assessment, trusted
[p.text for p in pages if p.trusted]
```

## Routes and reasons

| Route | Meaning | Reasons |
|---|---|---|
| `keep` | Index as is. | — |
| `repair` | Text is right but encoded or ordered badly; a deterministic fix exists. | `presentation_forms` (apply NFKC), `visual_order` (reverse each line), `unmapped_elongation` (delete U+FFFD), `bidi_controls` (delete embedding marks) |
| `reextract` | The extractor damaged correct source text; try another extractor. | `mixed_reading_order`, `lam_alef_transposition`, `lost_word_boundaries` |
| `ocr` | The text layer itself is wrong; read the pixels. | `same_script_substitution`, `unmapped_glyphs`, `legacy_encoding`, `quran_glyph_codes`, `no_text_layer` |

`quran_glyph_codes`: Quran text set in the King Fahd Complex page fonts (`QCF_P…`) stores
one glyph ID per word under Presentation Forms-A code points. NFKC would turn those IDs
into wrong words, so they are never sent to `repair`; take the verse from a canonical Quran
text or OCR it. The rest of the same text is still judged on its own letters.

A page takes the most severe route among its font runs, so one broken heading font next to
a healthy body font is reported precisely instead of being averaged away. A font whose runs
are too short to judge on any one page (running heads, headings, verse numbers) is judged
on its short runs pooled across the scanned pages; such font reports carry
`"scope": "document"`. Fonts are identified by their PDF name including the subset tag
(`ABCDEE+Lotus Linotype`), because two subsets of one typeface can map glyphs differently.

`scan` (raw text layer) ignores reading order, which depends on the extractor. `check`
(final extractor output) also reports order and spacing faults.

## How it works

1. Text is reduced to base Arabic letters (presentation forms decomposed, diacritics,
   tatweel and decorative letter runs removed).
2. Each line's reading direction is decided by comparing the model's score forwards and
   backwards, so mirrored text is not mistaken for corruption.
3. A 4-gram character model with interpolated Witten-Bell smoothing scores the corrected
   letters. Wrong glyph-to-letter maps produce improbable letter sequences (high bits per
   character) or isolated very improbable letters (spikes).
4. A second model trained without spaces separates "the letters are wrong" from "the
   extractor broke the word spacing".
5. Character-class checks catch private-use glyphs, raw `(cid:N)` codes, presentation
   forms, Quran glyph-ID fonts, and pre-Unicode encodings without any model. Pre-Unicode
   fonts land either on Latin-1 and symbol characters or on ASCII, where they read as
   Latin "words" with almost no vowels or with digits, symbols and case flips inside
   (`otsrqponmlkA{zvjihgf`, `h&c%G`); English text has about 40% vowels and few such words.

## Accuracy

### Real books

Full numbers: [`reports/benchmark.md`](reports/benchmark.md). 57 printed-edition PDFs with
a text layer, linked from al-Maktaba al-Shamela (up to six per subject category), up to 40
evenly spaced pages each: 2,280 pages. Labels come from Shamela's typed transcriptions,
not from harfix: a font run is `broken` when at most 35% of its words exist in those
transcriptions (or an English word list) and `clean` from 75% up. No OCR is involved. Of
24 labelled runs checked by hand, 23 matched their label and one was borderline.

The books are split by a hash of the PDF into 32 `dev` books, used when changing rules,
and 25 `test` books. On the test split:

| Unit | Precision | Recall | Labelled clean / broken |
|---|---:|---:|---:|
| Pages | 98.8% | 99.8% | 191 / 488 |
| Font runs | 98.7% | 98.0% | 435 / 747 |

More than half of the labelled pages have a broken text layer, mostly pre-Unicode fonts
and fonts with no Unicode map. Two rules added after 0.1.0 from dev books raised test
font-run recall from 92.4% to 98.0%: pre-Unicode fonts mapped onto ASCII digits and
punctuation, and U+FFFD elongation glyphs inside otherwise intact words (now `repair`
instead of `ocr`). Samples of two test books had been looked at before the split, so
the test numbers are close to, but not strictly, held out.

### Repair

Full numbers: [`reports/repair.md`](reports/repair.md). On the same Shamela PDFs, every
page `harfix repair` changed is scored by the share of its Arabic words a plain search
index would match in Shamela's transcriptions (only diacritics and tatweel removed):

| Extractor | Pages repaired | Median match before | Median match after | Pages worse |
|---|---:|---:|---:|---:|
| pdfminer.six (mostly visual order) | 453 | 20.0% | 90.3% | 0 |
| pdftotext (bidi marks, presentation forms, elongation glyphs) | 562 | 25.4% | 92.0% | 0 |

The bidi embedding marks pdftotext inserts sit on about half of its pages in this sample
and stick to the neighbouring words, so they alone hide many words from a search index.

### Decode

Full numbers: [`reports/font_decoder.md`](reports/font_decoder.md). A map learned from 597
pages of four `AXt…` / `Adv…` books, scored on three other books in the same fonts against
Shamela's typed text of the same pages, words as multisets:

| Book | Pages | `harfix decode` precision / recall | archive.org OCR (Tesseract) precision / recall |
|---|---:|---:|---:|
| 18 | 54 | 76.9% / 71.9% | 72.9% / 69.3% |
| 1575 | 169 | 84.0% / 77.4% | 61.6% / 54.5% |
| 1576 | 191 | 77.4% / 70.7% | 67.9% / 63.6% |

The packaged map is trained on all seven books.

### Synthetic corruptions

Full numbers: [`reports/calibration.md`](reports/calibration.md). Thresholds were fitted on
one held-out split of 462 public Arabic pages and measured on another, then raised
(`DOMAIN_FLOORS`) after inspecting clean runs in Egyptian court and statute PDFs.

On the test split, windows of at least 80 Arabic letters:

| Case | Flagged correctly |
|---|---:|
| Clean text left as `keep` (PDF scan / extractor output) | 100% / 99.5% |
| Whole font with a wrong letter map | 100% |
| Private-use glyphs, raw CID codes, Latin-1 legacy encodings, presentation forms | 100% |
| Quran glyph-ID fonts | 100% |
| ASCII legacy encodings (letters / digits and punctuation) | 96% / 92% |
| Unmapped elongation glyphs inside words | 97% (100% at ≥200 letters) |
| Mirrored lines detected (`check`) | 100% |
| Lam-alef transposition (`check`) | 90% (97% at ≥200 letters) |
| Lost word boundaries (`check`) | 99.8% |
| Padding letters inserted (seen in Egyptian court books) | 72% (87% at ≥500 letters) |
| Only 6 of 36 letters swapped | 40% (52% at ≥500 letters) |

## Limitations

- The model is trained on about 300 pages of modern standard Arabic. Classical, dialectal,
  or heavily domain-specific text scores higher; calibrate before relying on it there.
- Precision is preferred over recall: partial letter swaps and light padding are missed
  part of the time.
- `scan` cannot tell a text layer without word spaces from one with wrong letters: both
  are reported as `same_script_substitution`.
- A pre-Unicode font is caught only once its runs hold about 15 Latin-looking words or 8
  digit-and-symbol words; a font whose codes land on plain numbers is not caught.
- `unmapped_elongation` assumes U+FFFD inside a word that reads correctly without it was
  an elongation glyph. A lost letter whose word still reads as Arabic slips through.
- `check` splits text without form feeds at line ends, so a single very long line is
  judged as one piece.
- Scanned pages are routed to OCR but their image quality is not assessed.
- `decode` knows one family of pre-Unicode fonts (`AXt…` / `Adv…`, seven books). Verse
  text in its `Adv.QAL603` font is not decoded, and fonts that extract as raw glyph IDs
  (`(cid:N)`) are numbered per PDF, so their maps cannot be learned once for all books.
- PDF parsing uses pdfminer.six: about 0.1–0.2 s per page on the documents above.

## Roadmap

- More `decode` font families, including verse fonts and glyph-ID fonts (matched by glyph
  shape instead of code), and a comparison with a modern vision-language OCR model.
- Docling, LangChain and LlamaIndex integrations.
- A public benchmark of broken Arabic PDFs with labels per failure class.

## Rebuilding the model and thresholds

```bash
uv sync --group model
uv run python scripts/build_model.py    # pinned Hugging Face revisions, reproducible output
uv run python scripts/fetch_shamela.py  # needs the Shamela desktop app's catalogue
uv run python scripts/calibrate.py --pages 1-40 --pdf corpus/shamela/*.pdf

# real-book benchmark
uv run python scripts/fetch_shamela.py --out corpus/shamela_text --per-category 6 --text-only
uv run python scripts/benchmark.py fetch-text   # Shamela transcriptions, about 80 minutes
uv run python scripts/benchmark.py run
uv run python scripts/benchmark.py repair       # search matches before/after repair

# decode font maps (typed editions are fetched on first use)
uv run python scripts/fetch_shamela.py --out corpus/shamela_more --per-category 25 \
    --max-mb 30 --text-only --seed 1
uv run --group decoder python scripts/train_font_maps.py --train 9 10 19 1291 \
    --test 18 1575 1576
uv run --group decoder python scripts/train_font_maps.py \
    --train 9 10 18 19 1291 1575 1576 --save src/harfix/data/font_maps.json.gz
```

The Shamela PDFs and transcriptions are third-party works: keep them local, never commit
or redistribute them.

## License

Apache-2.0. The packaged character statistics are derived from Apache-2.0 datasets by
Misraj; see [`NOTICE`](NOTICE).
