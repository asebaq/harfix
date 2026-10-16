# harfix calibration report

Generated 2026-10-16 by `scripts/calibrate.py`. Model `3704fbc01115`.

Thresholds were fitted on the **calib** split; every rate below is measured on the
untouched **test** split (73 pages). Data: Misraj-DocOCR and
KITAB_pdf_to_markdown_reviewed (Apache-2.0), split by content hash.

## Thresholds

`fitted` targets a 0.5% false-flag rate per clean window. `used` raises some values
to `DOMAIN_FLOORS` (see `scripts/calibrate.py`) so clean Egyptian legal text in the
dev PDFs is not flagged.

| Name | Fitted | Used |
|---|---:|---:|
| `min_letters` | 80 | 80 |
| `substitution_bits` | 4.75 | 5.0 |
| `spike_bits` | 18.0 | 18.0 |
| `spike_rate` | 0.025 | 0.03 |
| `spike_min_letters` | 200 | 200 |
| `unspaced_bits` | 5.7 | 5.7 |
| `short_token_ratio` | 0.46 | 0.46 |
| `orientation_margin` | 0.5 | 0.5 |
| `presentation_form_ratio` | 0.05 | 0.05 |
| `unmapped_ratio` | 0.02 | 0.02 |
| `unmapped_min_glyphs` | 5 | 5 |
| `legacy_ratio` | 0.15 | 0.15 |
| `legacy_min_visible` | 30 | 30 |
| `transposition_ratio` | 0.27 | 0.27 |
| `mixed_order_min_share` | 0.2 | 0.2 |

## Detection on the test split

`scan` = PDF text-layer mode (character order unknown). `text` = extractor-output mode.
For `clean` and `visual order` in scan mode the rate is the share left as `keep`.
`text: any flag` is the share routed anywhere but `keep`, whatever the reason.

### Windows of ≥80 Arabic letters

| Case | Windows | Expected (scan) | scan | Expected (text) | text | text: any flag |
|---|---:|---|---:|---|---:|---:|
| clean | 416 | keep | 100.0% | keep | 99.5% | 0.5% |
| visual order | 416 | keep | 100.0% | visual_order | 100.0% | 100.0% |
| all letters substituted | 416 | same_script_substitution | 100.0% | same_script_substitution | 100.0% | 100.0% |
| 6 letters substituted | 416 | same_script_substitution | 40.4% | same_script_substitution | 40.4% | 40.9% |
| meem insertion | 416 | same_script_substitution | 72.1% | same_script_substitution | 71.9% | 73.1% |
| private-use glyphs | 416 | unmapped_glyphs | 100.0% | unmapped_glyphs | 100.0% | 100.0% |
| raw CID codes | 416 | unmapped_glyphs | 100.0% | unmapped_glyphs | 100.0% | 100.0% |
| legacy encoding | 416 | legacy_encoding | 100.0% | legacy_encoding | 100.0% | 100.0% |
| presentation forms | 416 | presentation_forms | 100.0% | presentation_forms | 100.0% | 100.0% |
| lam-alef transposition | 416 | - | n/a | lam_alef_transposition | 90.1% | 90.1% |
| lost word boundaries | 416 | - | n/a | lost_word_boundaries | 99.8% | 99.8% |

### Windows of ≥200 Arabic letters

| Case | Windows | Expected (scan) | scan | Expected (text) | text | text: any flag |
|---|---:|---|---:|---|---:|---:|
| clean | 222 | keep | 100.0% | keep | 99.5% | 0.5% |
| visual order | 222 | keep | 100.0% | visual_order | 100.0% | 100.0% |
| all letters substituted | 222 | same_script_substitution | 100.0% | same_script_substitution | 100.0% | 100.0% |
| 6 letters substituted | 222 | same_script_substitution | 50.0% | same_script_substitution | 50.0% | 50.9% |
| meem insertion | 222 | same_script_substitution | 77.5% | same_script_substitution | 77.5% | 77.9% |
| private-use glyphs | 222 | unmapped_glyphs | 100.0% | unmapped_glyphs | 100.0% | 100.0% |
| raw CID codes | 222 | unmapped_glyphs | 100.0% | unmapped_glyphs | 100.0% | 100.0% |
| legacy encoding | 222 | legacy_encoding | 100.0% | legacy_encoding | 100.0% | 100.0% |
| presentation forms | 222 | presentation_forms | 100.0% | presentation_forms | 100.0% | 100.0% |
| lam-alef transposition | 222 | - | n/a | lam_alef_transposition | 97.3% | 97.3% |
| lost word boundaries | 222 | - | n/a | lost_word_boundaries | 100.0% | 100.0% |

### Windows of ≥500 Arabic letters

| Case | Windows | Expected (scan) | scan | Expected (text) | text | text: any flag |
|---|---:|---|---:|---|---:|---:|
| clean | 96 | keep | 100.0% | keep | 99.0% | 1.0% |
| visual order | 96 | keep | 100.0% | visual_order | 100.0% | 100.0% |
| all letters substituted | 96 | same_script_substitution | 100.0% | same_script_substitution | 100.0% | 100.0% |
| 6 letters substituted | 96 | same_script_substitution | 52.1% | same_script_substitution | 52.1% | 52.1% |
| meem insertion | 96 | same_script_substitution | 86.5% | same_script_substitution | 86.5% | 86.5% |
| private-use glyphs | 96 | unmapped_glyphs | 100.0% | unmapped_glyphs | 100.0% | 100.0% |
| raw CID codes | 96 | unmapped_glyphs | 100.0% | unmapped_glyphs | 100.0% | 100.0% |
| legacy encoding | 96 | legacy_encoding | 100.0% | legacy_encoding | 100.0% | 100.0% |
| presentation forms | 96 | presentation_forms | 100.0% | presentation_forms | 100.0% | 100.0% |
| lam-alef transposition | 96 | - | n/a | lam_alef_transposition | 97.9% | 97.9% |
| lost word boundaries | 96 | - | n/a | lost_word_boundaries | 100.0% | 100.0% |

### Mixed reading order (whole pages)

Alternate lines reversed on 63 test pages: detected 88.9%; false `mixed_reading_order` flags on the same
pages unmodified: 0.0%.

## Real PDFs (dev)

Used to choose `DOMAIN_FLOORS`, so these are not an independent measurement. Per-font summary of runs with enough Arabic text to judge.

### كتاب قضاء النقض الجنائي - الجزء الأول - نقض الأحكام وإعادة المحاكمة - الإصدار الإلكتروني .pdf

30 pages scanned; page routes: keep=21, ocr=9.

| Font | Runs | Letters | Median bits/char | Routes |
|---|---:|---:|---:|---|
| SimplifiedArabic | 10 | 11431 | 3.27 | keep=10 |
| Arial-BoldMT | 7 | 10489 | 5.71 | ocr=6, keep=1 |
| SimplifiedArabic-Bold | 9 | 4057 | 4.02 | keep=9 |

### المستحدث 1.pdf

30 pages scanned; page routes: keep=30.

| Font | Runs | Letters | Median bits/char | Routes |
|---|---:|---:|---:|---|
| SimplifiedArabic | 26 | 30327 | 3.25 | keep=26 |
| SimplifiedArabic-Bold | 7 | 2357 | 3.48 | keep=7 |

### السنة 72  جنائى الكترونى.pdf

30 pages scanned; page routes: keep=23, ocr=7.

| Font | Runs | Letters | Median bits/char | Routes |
|---|---:|---:|---:|---|
| SimplifiedArabic | 24 | 29876 | 3.23 | keep=24 |
| Arial-BoldMT | 30 | 5160 | 3.24 | keep=30 |
| SimplifiedArabic-Bold | 9 | 3470 | 5.15 | ocr=7, keep=2 |

### labor_law_14_2025_ministry.pdf

30 pages scanned; page routes: repair=30.

| Font | Runs | Letters | Median bits/char | Routes |
|---|---:|---:|---:|---|
| SimplifiedArabic | 29 | 29330 | 3.15 | repair=29 |
| SimplifiedArabic-Bold | 4 | 415 | 3.4 | repair=4 |
| TimesNewRomanPSMT | 1 | 95 | 3.2 | repair=1 |

### 2012_Constitution_-_Arabic_Original.pdf

30 pages scanned; page routes: keep=30.

| Font | Runs | Letters | Median bits/char | Routes |
|---|---:|---:|---:|---|
| Simplified Arabic | 28 | 21299 | 3.2 | keep=28 |
| Simplified Arabic,Bold | 3 | 1347 | 3.21 | keep=3 |
| PT Bold Heading | 1 | 202 | 3.46 | keep=1 |

## Real PDFs (held-out)

Not used for any threshold. Per-font summary of runs with enough Arabic text to judge.

### كتاب قضاء النقض الجنائي - الجزء الثاني- نقض الأحكام والقضاء بالبراءة - الإصدار الإلكتروني .pdf

30 pages scanned; page routes: keep=21, ocr=9.

| Font | Runs | Letters | Median bits/char | Routes |
|---|---:|---:|---:|---|
| SimplifiedArabic | 11 | 14086 | 3.39 | keep=11 |
| Arial-BoldMT | 8 | 10763 | 5.69 | ocr=7, keep=1 |
| SimplifiedArabic-Bold | 8 | 2969 | 4.03 | keep=7, ocr=1 |

### المستحدث 2.pdf

30 pages scanned; page routes: keep=23, ocr=7.

| Font | Runs | Letters | Median bits/char | Routes |
|---|---:|---:|---:|---|
| SimplifiedArabic | 25 | 30093 | 3.2 | keep=25 |
| SimplifiedArabic-Bold | 10 | 3492 | 5.01 | keep=4, ocr=6 |

### المستحدث 5.pdf

30 pages scanned; page routes: keep=15, ocr=15.

| Font | Runs | Letters | Median bits/char | Routes |
|---|---:|---:|---:|---|
| Simplified Arabic | 15 | 14861 | 7.43 | ocr=15 |
| Times New Roman,Bold | 3 | 717 | 3.52 | keep=3 |
| PT Bold Heading | 4 | 617 | 3.84 | keep=4 |
| Simplified Arabic,Bold | 2 | 463 | 3.67 | keep=2 |
| Diwani Letter | 1 | 263 | 4.37 | keep=1 |
| Arial,Bold | 1 | 146 | 2.95 | keep=1 |

### السنة ٦٩ جنائى الكتروني.pdf

30 pages scanned; page routes: keep=27, ocr=3.

| Font | Runs | Letters | Median bits/char | Routes |
|---|---:|---:|---:|---|
| SimplifiedArabic | 25 | 31281 | 3.21 | keep=25 |
| Arial-BoldMT | 29 | 4959 | 3.23 | keep=29 |
| SimplifiedArabic-Bold | 8 | 3306 | 4.35 | ocr=3, keep=5 |

### السنة 74 جنائى الكترونى.pdf

30 pages scanned; page routes: keep=29, ocr=1.

| Font | Runs | Letters | Median bits/char | Routes |
|---|---:|---:|---:|---|
| SimplifiedArabic | 25 | 32783 | 3.21 | keep=25 |
| SimplifiedArabic-Bold | 28 | 7442 | 3.22 | keep=28 |
| Arial-BoldMT | 1 | 138 | 2.58 | keep=1 |

### Penal_Code_-_Arabic_Original.pdf

30 pages scanned; page routes: ocr=30.

| Font | Runs | Letters | Median bits/char | Routes |
|---|---:|---:|---:|---|
| Tahoma | 30 | 47465 | 8.1 | ocr=30 |

### Protest_Law_-_Arabic_Original.pdf

8 pages scanned; page routes: ocr=8.

| Font | Runs | Letters | Median bits/char | Routes |
|---|---:|---:|---:|---|
| unknown | 8 | 0 | None | ocr=8 |

## Limitations

- Corruptions are synthetic except for the real-PDF sections; real fonts can fail in
  patterns not simulated here. The real-PDF tables have no ground-truth labels.
- `DOMAIN_FLOORS` trade recall for precision: partial substitutions (a few swapped
  letters) and light padding are caught only part of the time.
- The model is trained on about 300 pages of modern standard Arabic. Classical or
  dialectal text scores higher and needs its own calibration before relying on it.
- Runs shorter than `min_letters` are not judged on their own; spike rates are only
  used from `spike_min_letters` up.
