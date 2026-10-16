# harfix

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
# from a clone of this repository (PyPI release pending)
uv sync            # or: pip install .
```

Python 3.10+. The only runtime dependency is `pdfminer.six`; the two character models
(~300 KiB) ship with the package.

## Use

Audit the text layer of PDFs:

```console
$ harfix scan --pages 3 --fail-on ocr -v Penal_Code_-_Arabic_Original.pdf
Penal_Code_-_Arabic_Original.pdf
  pages: ocr=1
  p3     ocr       same_script_substitution
         Tahoma                                   ocr       letters=1617 bits=8.184 same_script_substitution
         Tahoma,Bold                              keep      letters=54 bits=- insufficient_arabic_text
```

`--json` prints the full report; `--fail-on repair|reextract|ocr` turns the scan into a CI
or pipeline gate (exit code 1).

Check text produced by any extractor (Docling, pdftotext, Marker, an OCR engine):

```console
$ pdftotext -f 3 -l 3 labor_law_14_2025.pdf - | harfix check
repair: presentation_forms
  arabic_letters: 1111
  presentation_form_ratio: 0.9648
  ...
```

From Python:

```python
from harfix import assess_text, scan_pdf

report = scan_pdf("ruling.pdf", pages=range(1, 11))
for page in report.pages:
    if page.route != "keep":
        print(page.page, page.route, page.reasons)

verdict = assess_text(extracted_text)  # extractor output: checks reading order too
verdict.route, verdict.reasons, verdict.metrics
```

## Routes and reasons

| Route | Meaning | Reasons |
|---|---|---|
| `keep` | Index as is. | — |
| `repair` | Text is right but encoded or ordered badly; a deterministic fix exists. | `presentation_forms` (apply NFKC), `visual_order` (reverse each line) |
| `reextract` | The extractor damaged correct source text; try another extractor. | `mixed_reading_order`, `lam_alef_transposition`, `lost_word_boundaries` |
| `ocr` | The text layer itself is wrong; read the pixels. | `same_script_substitution`, `unmapped_glyphs`, `legacy_encoding`, `no_text_layer` |

A page takes the most severe route among its font runs, so one broken heading font next to
a healthy body font is reported precisely instead of being averaged away.

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
   forms, and pre-Unicode encodings without any model.

## Accuracy

Full numbers: [`reports/calibration.md`](reports/calibration.md). Thresholds were fitted on
one held-out split of 462 public Arabic pages and measured on another, then raised
(`DOMAIN_FLOORS`) after inspecting clean runs in a separate set of Egyptian legal PDFs.

On the test split, windows of at least 80 Arabic letters:

| Case | Flagged correctly |
|---|---:|
| Clean text left as `keep` (PDF scan / extractor output) | 100% / 99.5% |
| Whole font with a wrong letter map | 100% |
| Private-use glyphs, raw CID codes, legacy encodings, presentation forms | 100% |
| Mirrored lines detected (`check`) | 100% |
| Lam-alef transposition (`check`) | 90% (97% at ≥200 letters) |
| Lost word boundaries (`check`) | 99.8% |
| Padding letters inserted (seen in Egyptian court books) | 72% (87% at ≥500 letters) |
| Only 6 of 36 letters swapped | 40% (52% at ≥500 letters) |

On seven held-out Egyptian legal PDFs (188 pages, not used for any threshold), harfix
flagged the known-broken fonts of the Court of Cassation books, a Penal Code PDF whose
Tahoma text layer is entirely wrong, and a law published in a pre-Unicode font. Up to two
flagged runs per font and document were inspected by hand. That inspection found one false
positive class, Symbol-font bullets read as unmapped glyphs, which led to the Symbol
exclusion and the minimum unmapped-glyph count; every other inspected run was genuinely
broken. So these PDFs shaped two rules, though no threshold, and this is a spot check rather
than a labeled evaluation.

## Limitations

- The model is trained on about 300 pages of modern standard Arabic. Classical, dialectal,
  or heavily domain-specific text scores higher; calibrate before relying on it there.
- Precision is preferred over recall: partial letter swaps and light padding are missed
  part of the time.
- Runs under 80 Arabic letters are judged only as part of their page.
- Scanned pages are routed to OCR but their image quality is not assessed.
- PDF parsing uses pdfminer.six: about 0.1–0.2 s per page on the documents above.

## Roadmap

- Text-level repairs for the `repair` route (NFKC, line reversal) with provenance.
- Per-font decoder for legacy and custom Arabic fonts: OCR a few pages, learn the
  glyph-to-letter map, decode the rest of the document without OCR.
- Docling, LangChain and LlamaIndex integrations.
- A public benchmark of broken Arabic PDFs with labels per failure class.

## Rebuilding the model and thresholds

```bash
uv sync --group model
uv run python scripts/build_model.py    # pinned Hugging Face revisions, reproducible output
uv run python scripts/calibrate.py --pages 1-30 --dev-pdf ... --pdf ...
```

## License

Apache-2.0. The packaged character statistics are derived from Apache-2.0 datasets by
Misraj; see [`NOTICE`](NOTICE).
