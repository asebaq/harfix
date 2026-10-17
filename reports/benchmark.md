# harfix benchmark: Shamela books

Generated 2026-10-18 by `scripts/benchmark.py`.

Labels come from typed text, not from harfix: a font run is `clean` when at least
75% of its words occur in Shamela's transcriptions of the books (or in
an English word list), `broken` at 35% or less, `partial` in between;
runs with fewer than 8 countable words are unlabelled. Words containing
unmapped glyphs count as not found. See the script docstring for details.

A harfix verdict counts as a flag when the route is `reextract` or `ocr`; `repair`
means the letters are right, so it counts with `keep`. A flagged page whose flagging
runs are all too short to label is `unverified` and left out of the page scores.

Books: 57 with a PDF text layer and a typed text. Up to 40 pages per book, evenly spaced.

## Labels

| Unit | clean | broken | partial | unverified | unlabelled |
|---|---:|---:|---:|---:|---:|
| pages | 412 | 1162 | 485 | 83 | 138 |
| font runs | 815 | 1720 | 856 | - | - |

## harfix against the labels (clean and broken only)

| Unit | Flagged broken | Flagged clean | Missed broken | Kept clean | Precision | Recall |
|---|---:|---:|---:|---:|---:|---:|
| pages | 1160 | 15 | 2 | 397 | 98.7% | 99.8% |
| font runs | 1646 | 39 | 74 | 776 | 97.7% | 95.7% |

## Flagged font runs by reason

| Reason | clean | broken | partial |
|---|---:|---:|---:|
| `legacy_encoding` | 0 | 614 | 0 |
| `presentation_forms` | 105 | 108 | 95 |
| `quran_glyph_codes` | 6 | 35 | 27 |
| `same_script_substitution` | 20 | 277 | 493 |
| `unmapped_glyphs` | 13 | 1063 | 34 |

## Per book

| Shamela id | Pages | Labels (clean/broken/partial/unverified/unlabelled) | Flagged | Precision | Recall |
|---:|---:|---|---:|---:|---:|
| 1106 | 40 | 0/9/31/0/0 | 28 | 100.0% | 100.0% |
| 319+325+488+493+495+500+501+502+503+505+507+508+509+511 | 40 | 33/0/4/0/3 | 4 | n/a | n/a |
| 510+513+516+517+518+519+520+521 | 40 | 36/0/3/0/1 | 0 | n/a | n/a |
| 370 | 40 | 0/37/2/0/1 | 40 | 100.0% | 100.0% |
| 926 | 40 | 0/39/0/0/1 | 40 | 100.0% | 100.0% |
| 806 | 40 | 1/14/15/8/2 | 38 | 100.0% | 100.0% |
| 909 | 40 | 0/38/0/0/2 | 38 | 100.0% | 100.0% |
| 30095 | 40 | 5/3/30/2/0 | 7 | 100.0% | 100.0% |
| 937 | 40 | 0/38/0/0/2 | 38 | 100.0% | 100.0% |
| 525+526+528+530+531+532 | 40 | 37/0/2/0/1 | 1 | n/a | n/a |
| 371+372+373+374+375+376+377+378+379+381+382+383+385+386+387+388+389 | 40 | 32/1/4/0/3 | 3 | 100.0% | 100.0% |
| 1091 | 40 | 0/38/0/0/2 | 40 | 100.0% | 100.0% |
| 568 | 40 | 0/34/0/0/6 | 37 | 100.0% | 100.0% |
| 574 | 40 | 0/36/0/0/4 | 36 | 100.0% | 100.0% |
| 820 | 40 | 0/39/0/0/1 | 40 | 100.0% | 100.0% |
| 570 | 40 | 0/38/0/0/2 | 38 | 100.0% | 100.0% |
| 1095 | 40 | 0/38/0/0/2 | 38 | 100.0% | 100.0% |
| 800 | 40 | 8/8/14/9/1 | 26 | 100.0% | 100.0% |
| 1297 | 40 | 0/38/0/0/2 | 39 | 100.0% | 100.0% |
| 576 | 40 | 0/37/0/0/3 | 38 | 100.0% | 100.0% |
| 14572 | 40 | 0/37/0/0/3 | 40 | 100.0% | 100.0% |
| 138 | 40 | 0/28/7/1/4 | 36 | 100.0% | 100.0% |
| 938 | 40 | 0/39/0/0/1 | 40 | 100.0% | 100.0% |
| 17773 | 40 | 14/4/8/13/1 | 26 | 80.0% | 100.0% |
| 358+359+361+362+363+364+366+367+368+369 | 40 | 34/0/4/0/2 | 5 | n/a | n/a |
| 391+392+393+394+395+396+398+402+403+406+407+409+413+414 | 40 | 36/1/2/0/1 | 2 | n/a | 0.0% |
| 815 | 40 | 0/37/0/0/3 | 40 | 100.0% | 100.0% |
| 1258 | 40 | 0/39/0/0/1 | 40 | 100.0% | 100.0% |
| 1357 | 40 | 0/0/37/0/3 | 36 | n/a | n/a |
| 946 | 40 | 0/37/0/1/2 | 38 | 100.0% | 100.0% |
| 30631 | 40 | 1/3/34/2/0 | 13 | 100.0% | 100.0% |
| 139 | 40 | 32/1/6/0/1 | 1 | n/a | 0.0% |
| 9 | 40 | 0/37/0/0/3 | 38 | 100.0% | 100.0% |
| 18 | 40 | 0/27/0/0/13 | 34 | 100.0% | 100.0% |
| 1124 | 40 | 0/3/34/0/3 | 32 | 100.0% | 100.0% |
| 30628 | 40 | 0/39/0/0/1 | 40 | 100.0% | 100.0% |
| 1576 | 40 | 0/36/0/0/4 | 38 | 100.0% | 100.0% |
| 1230 | 40 | 1/0/35/0/4 | 7 | n/a | n/a |
| 1112 | 40 | 19/1/3/13/4 | 18 | 25.0% | 100.0% |
| 356 | 40 | 0/38/0/0/2 | 38 | 100.0% | 100.0% |
| 23 | 40 | 0/9/29/1/1 | 40 | 100.0% | 100.0% |
| 354 | 40 | 0/39/0/0/1 | 39 | 100.0% | 100.0% |
| 108 | 40 | 4/4/16/15/1 | 36 | 66.7% | 100.0% |
| 10 | 40 | 0/35/0/0/5 | 40 | 100.0% | 100.0% |
| 1573 | 40 | 0/39/0/0/1 | 40 | 100.0% | 100.0% |
| 30131 | 40 | 0/9/28/1/2 | 39 | 100.0% | 100.0% |
| 944 | 40 | 0/26/0/0/14 | 26 | 100.0% | 100.0% |
| 255 | 40 | 5/15/9/8/3 | 31 | 100.0% | 100.0% |
| 1477 | 40 | 0/18/21/0/1 | 38 | 100.0% | 100.0% |
| 538 | 40 | 0/37/0/0/3 | 37 | 100.0% | 100.0% |
| 1122 | 40 | 31/1/3/4/1 | 6 | 100.0% | 100.0% |
| 1452 | 40 | 0/32/7/0/1 | 40 | 100.0% | 100.0% |
| 1040 | 40 | 0/2/38/0/0 | 39 | 100.0% | 100.0% |
| 459+460+461+462+464+467+468+469+470+472+479+480+481+484 | 40 | 36/0/4/0/0 | 0 | n/a | n/a |
| 757 | 40 | 12/0/22/4/2 | 32 | 0.0% | n/a |
| 1238 | 40 | 0/4/30/1/5 | 39 | 100.0% | 100.0% |
| 415+424+425+426+428+430+436+438+439+440+441+442+443+444+446+447+448+449+450+451+453+454+455+456 | 40 | 35/0/3/0/2 | 5 | n/a | n/a |

## Limitations

- Labels test whether the extracted words exist, not their order or position: a run
  with correct words in a broken order is labelled clean.
- A garbled word occasionally matches a real one, so badly broken runs still find
  about 10-15% of their words; partial labels are left out of precision and recall.
- Book titles are omitted: see the local manifest for names and sources.
