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
| pages | 419 | 1161 | 485 | 77 | 138 |
| font runs | 815 | 1720 | 856 | - | - |

## harfix against the labels (clean and broken only)

Books are split by a hash of the PDF into `dev` (used when changing harfix rules) and
`test` (not looked at when changing rules). `all` is both.

| Split | Unit | Flagged broken | Flagged clean | Missed broken | Kept clean | Precision | Recall |
|---|---|---:|---:|---:|---:|---:|---:|
| dev | pages | 671 | 2 | 2 | 226 | 99.7% | 99.7% |
| dev | font runs | 958 | 18 | 15 | 362 | 98.2% | 98.5% |
| test | pages | 487 | 6 | 1 | 185 | 98.8% | 99.8% |
| test | font runs | 732 | 10 | 15 | 425 | 98.7% | 98.0% |
| all | pages | 1158 | 8 | 3 | 411 | 99.3% | 99.7% |
| all | font runs | 1690 | 28 | 30 | 787 | 98.4% | 98.3% |

## Flagged font runs by reason

| Reason | clean | broken | partial |
|---|---:|---:|---:|
| `legacy_encoding` | 0 | 663 | 0 |
| `presentation_forms` | 105 | 108 | 95 |
| `quran_glyph_codes` | 6 | 35 | 27 |
| `same_script_substitution` | 20 | 276 | 493 |
| `unmapped_elongation` | 11 | 3 | 16 |
| `unmapped_glyphs` | 2 | 1060 | 18 |

## Per book

| Shamela id | Split | Pages | Labels (clean/broken/partial/unverified/unlabelled) | Flagged | Precision | Recall |
|---:|---|---:|---|---:|---:|---:|
| 1106 | test | 40 | 0/9/31/0/0 | 28 | 100.0% | 100.0% |
| 319+325+488+493+495+500+501+502+503+505+507+508+509+511 | test | 40 | 33/0/4/0/3 | 4 | n/a | n/a |
| 510+513+516+517+518+519+520+521 | dev | 40 | 36/0/3/0/1 | 0 | n/a | n/a |
| 370 | dev | 40 | 0/37/2/0/1 | 40 | 100.0% | 100.0% |
| 926 | dev | 40 | 0/39/0/0/1 | 40 | 100.0% | 100.0% |
| 806 | dev | 40 | 1/14/14/9/2 | 38 | 100.0% | 100.0% |
| 909 | test | 40 | 0/38/0/0/2 | 38 | 100.0% | 100.0% |
| 30095 | test | 40 | 5/3/30/2/0 | 7 | 100.0% | 100.0% |
| 937 | dev | 40 | 0/38/0/0/2 | 38 | 100.0% | 100.0% |
| 525+526+528+530+531+532 | dev | 40 | 37/0/2/0/1 | 1 | n/a | n/a |
| 371+372+373+374+375+376+377+378+379+381+382+383+385+386+387+388+389 | dev | 40 | 32/1/4/0/3 | 3 | 100.0% | 100.0% |
| 1091 | dev | 40 | 0/38/0/0/2 | 40 | 100.0% | 100.0% |
| 568 | test | 40 | 0/34/0/0/6 | 37 | 100.0% | 100.0% |
| 574 | dev | 40 | 0/36/0/0/4 | 36 | 100.0% | 100.0% |
| 820 | test | 40 | 0/39/0/0/1 | 40 | 100.0% | 100.0% |
| 570 | dev | 40 | 0/38/0/0/2 | 38 | 100.0% | 100.0% |
| 1095 | dev | 40 | 0/38/0/0/2 | 38 | 100.0% | 100.0% |
| 800 | test | 40 | 8/8/14/9/1 | 26 | 100.0% | 100.0% |
| 1297 | test | 40 | 0/38/0/0/2 | 39 | 100.0% | 100.0% |
| 576 | test | 40 | 0/37/0/0/3 | 38 | 100.0% | 100.0% |
| 14572 | dev | 40 | 0/37/0/0/3 | 40 | 100.0% | 100.0% |
| 138 | dev | 40 | 0/28/7/1/4 | 36 | 100.0% | 100.0% |
| 938 | dev | 40 | 0/39/0/0/1 | 40 | 100.0% | 100.0% |
| 17773 | test | 40 | 19/4/9/7/1 | 17 | 80.0% | 100.0% |
| 358+359+361+362+363+364+366+367+368+369 | test | 40 | 34/0/4/0/2 | 5 | n/a | n/a |
| 391+392+393+394+395+396+398+402+403+406+407+409+413+414 | dev | 40 | 36/1/2/0/1 | 2 | n/a | 0.0% |
| 815 | dev | 40 | 0/37/0/0/3 | 40 | 100.0% | 100.0% |
| 1258 | test | 40 | 0/39/0/0/1 | 40 | 100.0% | 100.0% |
| 1357 | dev | 40 | 0/0/37/0/3 | 36 | n/a | n/a |
| 946 | dev | 40 | 0/37/0/1/2 | 38 | 100.0% | 100.0% |
| 30631 | test | 40 | 1/3/34/2/0 | 13 | 100.0% | 100.0% |
| 139 | test | 40 | 32/1/6/0/1 | 1 | n/a | 0.0% |
| 9 | dev | 40 | 0/37/0/0/3 | 38 | 100.0% | 100.0% |
| 18 | test | 40 | 0/27/0/0/13 | 34 | 100.0% | 100.0% |
| 1124 | dev | 40 | 0/3/34/0/3 | 32 | 100.0% | 100.0% |
| 30628 | dev | 40 | 0/39/0/0/1 | 40 | 100.0% | 100.0% |
| 1576 | test | 40 | 0/36/0/0/4 | 38 | 100.0% | 100.0% |
| 1230 | test | 40 | 1/0/35/0/4 | 7 | n/a | n/a |
| 1112 | test | 40 | 19/1/3/13/4 | 18 | 25.0% | 100.0% |
| 356 | test | 40 | 0/38/0/0/2 | 38 | 100.0% | 100.0% |
| 23 | dev | 40 | 0/9/29/1/1 | 40 | 100.0% | 100.0% |
| 354 | dev | 40 | 0/39/0/0/1 | 39 | 100.0% | 100.0% |
| 108 | test | 40 | 4/4/16/15/1 | 36 | 66.7% | 100.0% |
| 10 | test | 40 | 0/35/0/0/5 | 40 | 100.0% | 100.0% |
| 1573 | test | 40 | 0/39/0/0/1 | 40 | 100.0% | 100.0% |
| 30131 | dev | 40 | 0/9/28/1/2 | 39 | 100.0% | 100.0% |
| 944 | dev | 40 | 0/26/0/0/14 | 26 | 100.0% | 100.0% |
| 255 | dev | 40 | 6/14/9/8/3 | 29 | 100.0% | 92.9% |
| 1477 | test | 40 | 0/18/21/0/1 | 38 | 100.0% | 100.0% |
| 538 | test | 40 | 0/37/0/0/3 | 37 | 100.0% | 100.0% |
| 1122 | dev | 40 | 31/1/3/4/1 | 6 | 100.0% | 100.0% |
| 1452 | dev | 40 | 0/32/7/0/1 | 40 | 100.0% | 100.0% |
| 1040 | dev | 40 | 0/2/38/0/0 | 39 | 100.0% | 100.0% |
| 459+460+461+462+464+467+468+469+470+472+479+480+481+484 | dev | 40 | 36/0/4/0/0 | 0 | n/a | n/a |
| 757 | dev | 40 | 13/0/22/3/2 | 14 | 0.0% | n/a |
| 1238 | dev | 40 | 0/4/30/1/5 | 39 | 100.0% | 100.0% |
| 415+424+425+426+428+430+436+438+439+440+441+442+443+444+446+447+448+449+450+451+453+454+455+456 | test | 40 | 35/0/3/0/2 | 5 | n/a | n/a |

## Limitations

- Labels test whether the extracted words exist, not their order or position: a run
  with correct words in a broken order is labelled clean.
- A garbled word occasionally matches a real one, so badly broken runs still find
  about 10-15% of their words; partial labels are left out of precision and recall.
- Book titles are omitted: see the local manifest for names and sources.
