# Cipher solver prototype: fonts with a wrong Unicode map

Generated 2026-10-21 with `scripts/cipher_prototype.py`.

**Decision: no-go** for a per-book letter-substitution solver. It lifts the broken runs
only part of the way and damages clean ones.

## What was tested

Fonts whose ToUnicode map gives Arabic letters, but the wrong ones. If each glyph always
extracts as the same wrong letter, the font's text is a substitution cipher: the right
assignment is the one under which the text reads best under harfix's letter model, and no
typed text is needed.

- **Solver:** per book and font, the font's text from the benchmark pages; presentation
  forms decomposed, tatweel dropped, each line read in the direction its letters score
  better in. Each extracted character is reassigned to the letter that most improves the
  4-gram score of the text, one at a time, from two starts (the characters as they are, and
  a frequency match) plus three perturbed restarts. A reassignment must gain at least 1
  bit per occurrence of the character.
- **Cases:** the benchmark's font runs labelled broken that `scan` sends to `ocr` for
  `same_script_substitution`, with at least 400 letters: 20 runs in 13 books.
- **Controls:** 25 font runs labelled clean, which the solver should leave alone.
- **Scoring:** share of words found in Shamela's transcriptions (the benchmark's labelling
  rule), before and after.

## Results

| Runs | Count | Median share of words found, before → after | Runs worse by > 2 points |
|---|---:|---:|---:|
| Broken | 20 | 28% → 41% | 1 |
| Clean (controls) | 25 | 87% → 85% | 14 |

With a stricter threshold (2 bits per occurrence) the broken runs reach 40% and 11 controls
still get worse; with a looser one (0.5 bits) 37% and 16.

Best broken runs: 30131 `Sultan bold` 15% → 53%, 23 `adwa-assalaf` 34% → 56%, 138
`KFGQPCUthmanTahaNaskh` 3% → 42%. No broken run reached the 75% the benchmark calls clean.

## Why it falls short

- **The maps are not letter substitutions.** In book 1477 (`mylotus`) `سبحانه وتعالى`
  extracts as `سبحرنه وتعرك` and `المنافقين` as `امةرفقين`: ligature glyphs that draw two or
  three letters extract as one wrong character, so one character stands for different
  letter sequences. A one-to-one reassignment cannot express that.
- **Letters are missing or scattered.** In `Lotus-Light` and `loutsshamy` runs, glyphs
  extract as letters with spaces between them, or not at all; the text has lost
  information that no reassignment recovers.
- **The objective misleads on fragmented text.** On clean runs whose words pdfminer splits
  apart, reassigning rare letters (`خ`, `ذ`, `ش`) to frequent ones (`ل`, `م`, `و`) raises the
  letter-model score by more than 1 bit per occurrence, so the threshold does not protect
  them.

## Next

The wrong maps look consistent within a font family (the same wrong output for the same
ligature across a book). That is what the supervised decoder already learns for `AXt…` /
`Adv…` fonts: per glyph, nothing, one letter, or a two-letter ligature, aligned against
typed text. Training `scripts/train_font_maps.py` on these families (keyed by family and
extracted character, as now, but keeping families that extract as Arabic letters) is the
better route, where typed editions exist. Missing glyphs need the glyph codes themselves
(names or outlines), not the extracted text.
