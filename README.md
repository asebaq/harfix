<h1 align="center">
  <a href="https://github.com/asebaq/harfix">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/asebaq/harfix/main/docs/assets/cover_dark.svg">
      <img alt="harfix" src="https://raw.githubusercontent.com/asebaq/harfix/main/docs/assets/cover_light.svg" width="640">
    </picture>
  </a>
</h1>

<p align="center">
  <a href="https://github.com/asebaq/harfix/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/asebaq/harfix/actions/workflows/ci.yml/badge.svg"></a>
  <a href="https://pypi.org/project/harfix/"><img alt="PyPI version" src="https://img.shields.io/pypi/v/harfix?color=0F766E"></a>
  <a href="https://pypi.org/project/harfix/"><img alt="Python versions" src="https://img.shields.io/python/required-version-toml?tomlFilePath=https%3A%2F%2Fraw.githubusercontent.com%2Fasebaq%2Fharfix%2Fmain%2Fpyproject.toml"></a>
  <a href="https://pypistats.org/packages/harfix"><img alt="PyPI downloads" src="https://img.shields.io/pypi/dm/harfix"></a>
  <a href="https://github.com/asebaq/harfix/blob/main/LICENSE"><img alt="License: Apache-2.0" src="https://img.shields.io/github/license/asebaq/harfix"></a>
  <br/>
  <a href="https://github.com/astral-sh/ruff"><img alt="Ruff" src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json"></a>
  <a href="https://github.com/astral-sh/uv"><img alt="uv" src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json"></a>
  <img alt="Runtime dependency: pdfminer.six only" src="https://img.shields.io/badge/runtime%20deps-pdfminer.six-0F766E">
  <img alt="Language: Arabic" src="https://img.shields.io/badge/language-%D8%A7%D9%84%D8%B9%D8%B1%D8%A8%D9%8A%D8%A9-DFE0E5">
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
reextract: lam_alef_transposition, presentation_forms
  pages: keep=2, repair=3, reextract=2
  p4               repair    presentation_forms
  p5               repair    presentation_forms
  p6               reextract presentation_forms, lam_alef_transposition
  p9               repair    presentation_forms
  p11              reextract presentation_forms, lam_alef_transposition
```

Page numbers count from the start of the input; blank pages are skipped.

From Python:

```python
from harfix import assess_document, assess_text, scan_pdf

report = scan_pdf("book.pdf", pages=range(1, 11))
for page in report.pages:
    if page.route != "keep":
        print(page.page, page.route, page.reasons)

document = assess_document(extracted_text)  # extractor output, page by page
document.route, [(s.page, s.assessment.route) for s in document.segments]

verdict = assess_text(snippet)  # one piece of text: checks reading order too
```

## Routes and reasons

| Route | Meaning | Reasons |
|---|---|---|
| `keep` | Index as is. | — |
| `repair` | Text is right but encoded or ordered badly; a deterministic fix exists. | `presentation_forms` (apply NFKC), `visual_order` (reverse each line) |
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
| ASCII legacy encodings | 96% (100% at ≥500 letters) |
| Mirrored lines detected (`check`) | 100% |
| Lam-alef transposition (`check`) | 90% (97% at ≥200 letters) |
| Lost word boundaries (`check`) | 99.8% |
| Padding letters inserted (seen in Egyptian court books) | 72% (87% at ≥500 letters) |
| Only 6 of 36 letters swapped | 40% (52% at ≥500 letters) |

Real books: `scripts/fetch_shamela.py` samples printed-edition PDFs listed in
al-Maktaba al-Shamela (two per subject category, seed 0); none was used for any threshold.
Of 46 distinct books (first 40 pages each), 33 are image-only scans (`no_text_layer`). Of
the 13 with a text layer, 12 have fonts flagged on at least some pages: pre-Unicode `AXt`,
`Adv…` and `MCS` fonts (`legacy_encoding`), fonts with no Unicode map at all
(`unmapped_glyphs`), a `QCF_P206` verse font (`quran_glyph_codes`), Lotus and Uthman Taha
fonts whose text is fragmented with stray dammas (`same_script_substitution`), Yakout text
stored as presentation forms (`repair`), and OCR text layers with garbled title pages.
Samples of flagged fonts in 8 of those 12 books, covering every kind above, were inspected
by hand: all were genuinely broken, but one was misattributed (a Lotus layer with correct
letters and no word spaces is reported as `same_script_substitution`, see Limitations).
The inspection also caught stray Lotus ligature glyphs misread as a Quran font, which led
to the consecutive-code-point condition. This is a spot check, not a labeled evaluation.

## Limitations

- The model is trained on about 300 pages of modern standard Arabic. Classical, dialectal,
  or heavily domain-specific text scores higher; calibrate before relying on it there.
- Precision is preferred over recall: partial letter swaps and light padding are missed
  part of the time.
- `scan` cannot tell a text layer without word spaces from one with wrong letters: both
  are reported as `same_script_substitution`.
- A pre-Unicode font is caught only once its runs hold about 15 Latin-looking words, and a
  font mapped entirely onto digits and punctuation is not caught at all.
- `check` splits text without form feeds at line ends, so a single very long line is
  judged as one piece.
- Scanned pages are routed to OCR but their image quality is not assessed.
- PDF parsing uses pdfminer.six: about 0.1–0.2 s per page on the documents above.

## Roadmap

- Text-level repairs for the `repair` route (NFKC, line reversal) with provenance.
- Per-font decoder for legacy and custom Arabic fonts: learn each font's glyph-to-letter
  map once (from a typed edition of the same book, a library of known fonts, or the letter
  model itself, with OCR only as a fallback), then decode the whole document.
- Docling, LangChain and LlamaIndex integrations.
- A public benchmark of broken Arabic PDFs with labels per failure class.

## Rebuilding the model and thresholds

```bash
uv sync --group model
uv run python scripts/build_model.py    # pinned Hugging Face revisions, reproducible output
uv run python scripts/fetch_shamela.py  # needs the Shamela desktop app's catalogue
uv run python scripts/calibrate.py --pages 1-40 --pdf corpus/shamela/*.pdf
```

The Shamela PDFs are third-party works: keep them local, never commit or redistribute them.

## License

Apache-2.0. The packaged character statistics are derived from Apache-2.0 datasets by
Misraj; see [`NOTICE`](NOTICE).
