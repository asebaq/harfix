# harfix calibration report

Generated 2026-10-18 by `scripts/calibrate.py`. Model `3704fbc01115`.

Thresholds were fitted on the **calib** split; every rate below is measured on the
untouched **test** split (73 pages). Data: Misraj-DocOCR and
KITAB_pdf_to_markdown_reviewed (Apache-2.0), split by content hash.

## Thresholds

`fitted` targets a 0.5% false-flag rate per clean window. `used` raises some values
to `DOMAIN_FLOORS` (see `scripts/calibrate.py`), chosen so clean Egyptian court and
statute PDFs are not flagged.

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
| `latin_min_words` | 15 | 15 |
| `latin_vowel_ratio` | 0.25 | 0.25 |
| `latin_irregular_ratio` | 0.3 | 0.3 |
| `symbol_min_words` | 8 | 8 |
| `symbol_word_ratio` | 0.4 | 0.4 |
| `quran_min_forms` | 8 | 8 |
| `quran_ligature_share` | 0.5 | 0.5 |
| `quran_short_run_share` | 0.6 | 0.6 |
| `quran_consecutive_share` | 0.5 | 0.5 |
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
| ASCII legacy encoding | 416 | legacy_encoding | 96.4% | legacy_encoding | 96.4% | 96.4% |
| digit legacy encoding | 416 | legacy_encoding | 92.5% | legacy_encoding | 92.5% | 92.5% |
| unmapped elongation | 416 | unmapped_elongation | 97.4% | unmapped_elongation | 97.4% | 97.4% |
| Quran glyph codes | 416 | quran_glyph_codes | 100.0% | quran_glyph_codes | 100.0% | 100.0% |
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
| ASCII legacy encoding | 222 | legacy_encoding | 99.5% | legacy_encoding | 99.5% | 99.5% |
| digit legacy encoding | 222 | legacy_encoding | 92.8% | legacy_encoding | 92.8% | 92.8% |
| unmapped elongation | 222 | unmapped_elongation | 100.0% | unmapped_elongation | 100.0% | 100.0% |
| Quran glyph codes | 222 | quran_glyph_codes | 100.0% | quran_glyph_codes | 100.0% | 100.0% |
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
| ASCII legacy encoding | 96 | legacy_encoding | 100.0% | legacy_encoding | 100.0% | 100.0% |
| digit legacy encoding | 96 | legacy_encoding | 92.7% | legacy_encoding | 92.7% | 92.7% |
| unmapped elongation | 96 | unmapped_elongation | 100.0% | unmapped_elongation | 100.0% | 100.0% |
| Quran glyph codes | 96 | quran_glyph_codes | 100.0% | quran_glyph_codes | 100.0% | 100.0% |
| presentation forms | 96 | presentation_forms | 100.0% | presentation_forms | 100.0% | 100.0% |
| lam-alef transposition | 96 | - | n/a | lam_alef_transposition | 97.9% | 97.9% |
| lost word boundaries | 96 | - | n/a | lost_word_boundaries | 100.0% | 100.0% |

### Mixed reading order (whole pages)

Alternate lines reversed on 63 test pages: detected 88.9%; false `mixed_reading_order` flags on the same
pages unmodified: 0.0%.

## Real PDFs (held-out)

Not used for any threshold. Per-font summary of runs with enough Arabic text to judge.

### تحصيل عين الذهب من معدن جوهر الأدب في علم مجازات العرب (Shamela 1207, الأدب)

40 pages scanned; page routes: ocr=40.

| Font | Runs | Letters | Median bits/char | Routes |
|---|---:|---:|---:|---|

### القصيدة العجيبة والمفردة الغريبة ذات الأسئلة المفحمة والمعاني المحكمة (Shamela 94, الأدب)

40 pages scanned; page routes: keep=1, ocr=39.

| Font | Runs | Letters | Median bits/char | Routes |
|---|---:|---:|---:|---|

### أخبار قبائل الخزرج (Shamela 948, الأنساب)

40 pages scanned; page routes: keep=1, ocr=39.

| Font | Runs | Letters | Median bits/char | Routes |
|---|---:|---:|---:|---|

### الإنباه على قبائل الرواة - ت الإبياري (Shamela 6696, الأنساب)

40 pages scanned; page routes: ocr=40.

| Font | Runs | Letters | Median bits/char | Routes |
|---|---:|---:|---:|---|

### الرحلة إلى إفريقيا (Shamela 20555, البلدان والرحلات)

40 pages scanned; page routes: ocr=40.

| Font | Runs | Letters | Median bits/char | Routes |
|---|---:|---:|---:|---|

### رحلة الحج إلى بيت الله الحرام (Shamela 292, البلدان والرحلات)

40 pages scanned; page routes: ocr=40.

| Font | Runs | Letters | Median bits/char | Routes |
|---|---:|---:|---:|---|

### مرويات كتاب أخبار المدينة جمع وتوثيق ودراسة (Shamela 993, التاريخ)

40 pages scanned; page routes: ocr=40.

| Font | Runs | Letters | Median bits/char | Routes |
|---|---:|---:|---:|---|

### الإتقان في ضوابط تسجيل القرآن (Shamela 937, التجويد والقراءات)

40 pages scanned; page routes: keep=6, ocr=34.

| Font | Runs | Letters | Median bits/char | Routes |
|---|---:|---:|---:|---|
| ACEKWL+HeshamNormal | 18 | 0 | None | ocr=18 |
| APFNBY+SimplifiedArabic,Bold (short runs, pooled) | 21 | 0 | None | ocr=21 |
| BHQZCA+MCSTaybahS_Unormal. | 34 | 0 | None | ocr=34 |
| AKAKYG+SimplifiedArabic | 34 | 0 | None | ocr=34 |
| ASJHLP+AGAArabesque (short runs, pooled) | 17 | 0 | None | ocr=17 |
| ACEKWL+HeshamNormal (short runs, pooled) | 16 | 0 | None | ocr=16 |
| APFNBY+SimplifiedArabic,Bold | 13 | 0 | None | ocr=13 |
| ASJHLP+AGAArabesque | 2 | 0 | None | ocr=2 |

### التعليق على «الأربعين في التصوف» للسلمي - ضمن «آثار المعلمي» (Shamela 413, التخريج والأطراف)

40 pages scanned; page routes: keep=37, ocr=3.

| Font | Runs | Letters | Median bits/char | Routes |
|---|---:|---:|---:|---|
| UUAQUL+CourierNewPSMT | 37 | 27403 | 3.4 | ocr=1, keep=36 |

### الأثر الثمين في نصرة عائشة - رضي الله عنها - أم المؤمنين (Shamela 539, التراجم والطبقات)

40 pages scanned; page routes: ocr=40.

| Font | Runs | Letters | Median bits/char | Routes |
|---|---:|---:|---:|---|

### تيسير اللطيف المنان في خلاصة تفسير القرآن - ط الأوقاف السعودية (Shamela 31363, التفسير)

40 pages scanned; page routes: ocr=40.

| Font | Runs | Letters | Median bits/char | Routes |
|---|---:|---:|---:|---|

### متون طالب العلم - الإضافية - 8 (Shamela 1101, الجوامع)

40 pages scanned; page routes: keep=2, ocr=38.

| Font | Runs | Letters | Median bits/char | Routes |
|---|---:|---:|---:|---|
| unknown | 38 | 0 | None | ocr=38 |

### أدب الطلب ومنتهى الأرب - ت الخشت (Shamela 6854, الرقائق والآداب والأذكار)

40 pages scanned; page routes: ocr=40.

| Font | Runs | Letters | Median bits/char | Routes |
|---|---:|---:|---:|---|

### حياة السلف بين القول والعمل (Shamela 17505, الرقائق والآداب والأذكار)

40 pages scanned; page routes: ocr=40.

| Font | Runs | Letters | Median bits/char | Routes |
|---|---:|---:|---:|---|

### بذل النصائح الشرعية فيما على السلطان وولاة الأمور وسائر الرعية (Shamela 36111, السياسة الشرعية والقضاء)

40 pages scanned; page routes: ocr=40.

| Font | Runs | Letters | Median bits/char | Routes |
|---|---:|---:|---:|---|

### بحث في قصة بني هشام بن المغيرة واستئذانهم النبي - صلى الله عليه وسلم - أن يزوجوا عليا رضي الله عنه - ضمن «آثار المعلمي» (Shamela 484, السيرة النبوية)

40 pages scanned; page routes: keep=38, ocr=2.

| Font | Runs | Letters | Median bits/char | Routes |
|---|---:|---:|---:|---|
| QKJVKI+CourierNewPSMT | 38 | 28910 | 3.37 | keep=38 |
| QKJVKI+CourierNewPSMT (short runs, pooled) | 2 | 120 | 5.28 | ocr=2 |

### التعليق على الرحيق المختوم (Shamela 14572, السيرة النبوية)

40 pages scanned; page routes: keep=1, ocr=39.

| Font | Runs | Letters | Median bits/char | Routes |
|---|---:|---:|---:|---|
| unknown | 35 | 0 | None | ocr=35 |
| unknown (short runs, pooled) | 3 | 0 | None | ocr=3 |

### مختصر متن الكافي في العروض والقوافي - ضمن «آثار المعلمي» (Shamela 511, العروض والقوافي)

40 pages scanned; page routes: keep=34, ocr=6.

| Font | Runs | Letters | Median bits/char | Routes |
|---|---:|---:|---:|---|
| CSAYRU+CourierNewPSMT | 32 | 21291 | 3.45 | ocr=1, keep=31 |
| CSAYRU+CourierNewPSMT (short runs, pooled) | 3 | 125 | 4.29 | keep=3 |

### الحنيفية والعرب - ضمن «آثار المعلمي» (Shamela 362, العقيدة)

40 pages scanned; page routes: keep=37, ocr=3.

| Font | Runs | Letters | Median bits/char | Routes |
|---|---:|---:|---:|---|
| YDVGPN+CourierNewPSMT | 37 | 29562 | 3.39 | ocr=1, keep=36 |

### طلبة الطلبة (Shamela 6039, الغريب والمعاجم)

40 pages scanned; page routes: ocr=40.

| Font | Runs | Letters | Median bits/char | Routes |
|---|---:|---:|---:|---|

### المغرب في ترتيب المعرب - ط الكتاب العربي (Shamela 8459, الغريب والمعاجم)

40 pages scanned; page routes: ocr=40.

| Font | Runs | Letters | Median bits/char | Routes |
|---|---:|---:|---:|---|

### المنتقى من فتاوى الأئمة الأعلام (Shamela 30275, الفتاوى)

40 pages scanned; page routes: ocr=40.

| Font | Runs | Letters | Median bits/char | Routes |
|---|---:|---:|---:|---|

### الدرر الثرية من الفتاوى البازية (Shamela 815, الفتاوى)

40 pages scanned; page routes: ocr=40.

| Font | Runs | Letters | Median bits/char | Routes |
|---|---:|---:|---:|---|
| AJFOIV+LotusLinotype | 33 | 21538 | 6.31 | ocr=33 |
| AJFOIW+LotusLinotype | 25 | 2599 | 7.64 | ocr=25 |
| AJFOIZ+LotusLinotype,Bold | 11 | 1312 | 6.57 | ocr=11 |
| AJFOIZ+LotusLinotype,Bold (short runs, pooled) | 15 | 608 | 6.31 | ocr=15 |
| AJFOIW+LotusLinotype (short runs, pooled) | 8 | 529 | 7.81 | ocr=8 |
| AJFOJA+LotusLinotype,Bold (short runs, pooled) | 21 | 300 | 6.83 | ocr=21 |
| AJFOIQ+TraditionalArabic,Bold | 1 | 196 | 5.11 | ocr=1 |
| AJFOIJ+AL-Mateen | 8 | 0 | None | ocr=8 |
| AJFOIN+AL-Hor | 39 | 0 | None | ocr=39 |

### الموفي بمعرفة التصوف والصوفي (Shamela 97, الفرق والردود)

40 pages scanned; page routes: keep=2, ocr=38.

| Font | Runs | Letters | Median bits/char | Routes |
|---|---:|---:|---:|---|

### الانتصار للصحب والآل من افتراءات السماوي الضال (Shamela 21551, الفرق والردود)

40 pages scanned; page routes: ocr=40.

| Font | Runs | Letters | Median bits/char | Routes |
|---|---:|---:|---:|---|

### مختصر خوقير في فقه الإمام أحمد (Shamela 9, الفقه الحنبلي)

40 pages scanned; page routes: keep=7, ocr=33.

| Font | Runs | Letters | Median bits/char | Routes |
|---|---:|---:|---:|---|
| AAALLJ+AXtManalBold | 1 | 0 | None | ocr=1 |
| AAALLK+AXtShareQ | 1 | 0 | None | ocr=1 |
| AAALLL+AXtManal | 1 | 0 | None | ocr=1 |
| AAALLM+AXtManalBLack | 1 | 0 | None | ocr=1 |
| AAALMI+Font575 (short runs, pooled) | 31 | 0 | None | ocr=31 |
| AAALMJ+Adv.QAL603 (short runs, pooled) | 31 | 0 | None | ocr=31 |
| AAALMH+Font158 | 22 | 0 | None | ocr=22 |
| AAALMF+Adv_FloraLa | 25 | 0 | None | ocr=25 |
| AAALMG+Font159 | 17 | 0 | None | ocr=17 |
| AAALML+Adv_Lots_Ba | 1 | 0 | None | ocr=1 |
| AAALNC+Font143 (short runs, pooled) | 17 | 0 | None | ocr=17 |
| AAALND+Adv_FloraBa (short runs, pooled) | 17 | 0 | None | ocr=17 |
| AAALNE+Font144 (short runs, pooled) | 17 | 0 | None | ocr=17 |
| AAALMF+Adv_FloraLa (short runs, pooled) | 3 | 0 | None | ocr=3 |
| AAALMH+Font158 (short runs, pooled) | 6 | 0 | None | ocr=6 |

### التصحيح والترجيح على مختصر القدوري (Shamela 985, الفقه الحنفي)

40 pages scanned; page routes: ocr=40.

| Font | Runs | Letters | Median bits/char | Routes |
|---|---:|---:|---:|---|

### المخارج في الحيل - من الأصل لمحمد بن الحسن - ط الثقافة الدينية (Shamela 18264, الفقه الحنفي)

40 pages scanned; page routes: ocr=40.

| Font | Runs | Letters | Median bits/char | Routes |
|---|---:|---:|---:|---|

### مختصر المزني - ط الفكر بآخر كتاب الأم (Shamela 1661, الفقه الشافعي)

40 pages scanned; page routes: ocr=40.

| Font | Runs | Letters | Median bits/char | Routes |
|---|---:|---:|---:|---|

### نهاية التدريب نظم غاية التقريب - ت جراد (Shamela 1124, الفقه الشافعي)

40 pages scanned; page routes: keep=4, ocr=36.

| Font | Runs | Letters | Median bits/char | Routes |
|---|---:|---:|---:|---|
| ABCDEE+Lotus Linotype | 32 | 18076 | 5.1 | keep=12, ocr=20 |
| ABCDEE+AAA GoldenLotus | 4 | 1662 | 4.28 | keep=4 |
| ABCDEE+AAA GoldenLotus (short runs, pooled) | 30 | 873 | 3.59 | keep=30 |
| ABCDEE+KFGQPC Uthman Taha Naskh,Bold (short runs, pooled) | 20 | 533 | 5.0 | ocr=20 |
| BCDKEE+KFGQPCUthmanTahaNaskh | 1 | 137 | 5.11 | ocr=1 |
| ABCDEE+QCF_P206 | 1 | 0 | None | ocr=1 |

### الاختيارات الفقهية لشيخ الإسلام ابن تيمية لدى تلاميذه (Shamela 132619, الفقه العام)

40 pages scanned; page routes: ocr=40.

| Font | Runs | Letters | Median bits/char | Routes |
|---|---:|---:|---:|---|

### اختيارات شيخ الإسلام ابن تيمية لابن عبد الهادي (Shamela 147673, الفقه العام)

40 pages scanned; page routes: ocr=40.

| Font | Runs | Letters | Median bits/char | Routes |
|---|---:|---:|---:|---|

### الأحكام لعبد الملك بن حبيب (Shamela 1168, الفقه المالكي)

40 pages scanned; page routes: ocr=40.

| Font | Runs | Letters | Median bits/char | Routes |
|---|---:|---:|---:|---|

### عيون الأدلة في مسائل الخلاف بين فقهاء الأمصار - كتاب الطهارة - ط جامعة الإمام (Shamela 14608, الفقه المالكي)

40 pages scanned; page routes: ocr=40.

| Font | Runs | Letters | Median bits/char | Routes |
|---|---:|---:|---:|---|

### مختصر «المغالطات المنطقية» (Shamela 1113, المنطق)

40 pages scanned; page routes: ocr=40.

| Font | Runs | Letters | Median bits/char | Routes |
|---|---:|---:|---:|---|

### المغالطات المنطقية (Shamela 1112, المنطق)

40 pages scanned; page routes: keep=5, repair=21, ocr=14.

| Font | Runs | Letters | Median bits/char | Routes |
|---|---:|---:|---:|---|
| BIJGXK+YakoutLinotypeLight-Regular | 32 | 34537 | 4.03 | ocr=3, repair=29 |
| ALBHVB+YakoutLinotypeLight-Bold (short runs, pooled) | 14 | 350 | 3.69 | repair=14 |
| AQFMWP+YakoutLinotypeLight-Regular | 1 | 330 | 5.87 | ocr=1 |
| ZZCHLA+LucidaNewMath-Symbol (short runs, pooled) | 7 | 0 | None | ocr=7 |
| ZZCHLA+LucidaNewMath-Symbol | 2 | 0 | None | ocr=2 |

### التكملة للفارسي (Shamela 1165, النحو والصرف)

40 pages scanned; page routes: keep=1, ocr=39.

| Font | Runs | Letters | Median bits/char | Routes |
|---|---:|---:|---:|---|

### تصحيحات وتعليقات على سبل السلام للأمير الصنعاني - ضمن «آثار المعلمي» (Shamela 518, شروح الحديث)

40 pages scanned; page routes: keep=38, ocr=2.

| Font | Runs | Letters | Median bits/char | Routes |
|---|---:|---:|---:|---|
| MAVLIP+CourierNewPSMT | 37 | 31485 | 3.24 | keep=37 |

### الرحلة في طلب الحديث - ت عتر (Shamela 13020, علوم الحديث)

40 pages scanned; page routes: ocr=40.

| Font | Runs | Letters | Median bits/char | Routes |
|---|---:|---:|---:|---|

### القواعد والضوابط الفقهية المتضمنة للتيسير (Shamela 7270, علوم الفقه والقواعد الفقهية)

40 pages scanned; page routes: ocr=40.

| Font | Runs | Letters | Median bits/char | Routes |
|---|---:|---:|---:|---|

### النبأ العظيم - ت عمرو الشرقاوي (Shamela 1470, علوم القرآن وأصول التفسير)

40 pages scanned; page routes: ocr=40.

| Font | Runs | Letters | Median bits/char | Routes |
|---|---:|---:|---:|---|

### الفهارس العلمية لآثار الإمام ابن قيم الجوزية (Shamela 458, فهارس الكتب والأدلة)

40 pages scanned; page routes: ocr=40.

| Font | Runs | Letters | Median bits/char | Routes |
|---|---:|---:|---:|---|

### أسماء الكتب المتمم لكشف الظنون (Shamela 10734, فهارس الكتب والأدلة)

40 pages scanned; page routes: ocr=40.

| Font | Runs | Letters | Median bits/char | Routes |
|---|---:|---:|---:|---|

### منهج الصحابة في دعوة المشركين من غير أهل الكتاب (Shamela 600, كتب عامة)

40 pages scanned; page routes: ocr=40.

| Font | Runs | Letters | Median bits/char | Routes |
|---|---:|---:|---:|---|

### الصحيح المنتخل من كلام الأولين في بدع العمل (Shamela 1246, كتب عامة)

40 pages scanned; page routes: ocr=40.

| Font | Runs | Letters | Median bits/char | Routes |
|---|---:|---:|---:|---|

### رسالة في توسعة المسعى بين الصفا والمروة - ضمن «آثار المعلمي» (Shamela 446, مسائل فقهية)

40 pages scanned; page routes: keep=37, ocr=3.

| Font | Runs | Letters | Median bits/char | Routes |
|---|---:|---:|---:|---|
| UHEAPU+CourierNewPSMT | 37 | 27576 | 3.31 | ocr=1, keep=36 |

## Limitations

- Corruptions are synthetic except for the real-PDF sections; real fonts can fail in
  patterns not simulated here. The real-PDF tables have no ground-truth labels.
- `DOMAIN_FLOORS` trade recall for precision: partial substitutions (a few swapped
  letters) and light padding are caught only part of the time.
- The model is trained on about 300 pages of modern standard Arabic. Classical or
  dialectal text scores higher and needs its own calibration before relying on it.
- Runs shorter than `min_letters` are judged by pooling the font's short runs across
  the scanned pages; spike rates are only used from `spike_min_letters` up.
- Real PDFs are only those with a text layer the scan can judge; scanned books are
  routed to `ocr` as `no_text_layer` and say nothing about detection accuracy.
