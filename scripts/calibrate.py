"""Choose decision thresholds on held-out clean text and measure detection on corruptions.

Usage:
    uv run --group model python scripts/calibrate.py [--pdf FILE ... --pages 1-30]

Reads build/pages.jsonl from build_model.py. Thresholds are fitted on the "calib" split and
every reported rate is measured on the untouched "test" split. Writes
src/harfix/data/thresholds.json and reports/calibration.md.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import random
import statistics
from collections import Counter, defaultdict
from collections.abc import Callable
from pathlib import Path

import arabic_reshaper

from harfix.detect import Thresholds, assess_text, measure
from harfix.model import default_models
from harfix.normalize import ARABIC_LETTERS, BOUNDARY, letters_only

ROOT = Path(__file__).resolve().parent.parent
LETTERS = sorted(ARABIC_LETTERS)
WINDOW_SIZES = (80, 200, 500)
TARGET_FALSE_FLAG = 0.005  # per window, on clean text, at the smallest window size

# Minimums applied after fitting. The fitted values come from modern-standard-Arabic pages;
# clean runs in the dev PDFs (Egyptian court and statute publications: headings, tables of
# contents, legal vocabulary) scored up to 4.81 bits/char and 0.025 spike rate, so the
# synthetic fit alone would flag them. Revisit these whenever the dev set changes.
DOMAIN_FLOORS = {"substitution_bits": 5.0, "spike_rate": 0.03}


# ---------------------------------------------------------------- windows


def letter_count(text: str) -> int:
    return sum(1 for ch in letters_only(text) if ch != BOUNDARY)


def windows(text: str, size: int) -> list[str]:
    """Consecutive line groups holding at least `size` Arabic letters."""
    out, current, count = [], [], 0
    for line in text.splitlines():
        n = letter_count(line)
        if not n:
            continue
        current.append(line)
        count += n
        if count >= size:
            out.append("\n".join(current))
            current, count = [], 0
    return out


# ---------------------------------------------------------------- corruptions


def _rng(text: str, salt: str) -> random.Random:
    return random.Random(hashlib.sha256((salt + text).encode("utf-8")).hexdigest())


def _remap(text: str, table: dict[str, str]) -> str:
    return "".join(table.get(ch, ch) for ch in text)


def substitute_all(text: str) -> str:
    rng = _rng(text, "all")
    shuffled = LETTERS[:]
    rng.shuffle(shuffled)
    return _remap(text, dict(zip(LETTERS, shuffled, strict=True)))


def substitute_some(text: str, k: int = 6) -> str:
    rng = _rng(text, f"some{k}")
    chosen = rng.sample(LETTERS, k)
    rotated = chosen[1:] + chosen[:1]
    return _remap(text, dict(zip(chosen, rotated, strict=True)))


def meem_insertion(text: str) -> str:
    """Pattern seen in the Court of Cassation books: padding glyphs mapped to meem."""
    rng = _rng(text, "meem")
    out = []
    for ch in text:
        out.append(ch)
        if ch in ARABIC_LETTERS and rng.random() < 0.2:
            out.append("م" * rng.randint(1, 3))
    return "".join(out)


def private_use(text: str) -> str:
    return _remap(text, {ch: chr(0xE000 + i) for i, ch in enumerate(LETTERS)})


def cid_codes(text: str) -> str:
    """Font without a ToUnicode map: pdfminer emits raw glyph codes."""
    return _remap(text, {ch: f"(cid:{i + 3})" for i, ch in enumerate(LETTERS)})


def legacy_encoding(text: str) -> str:
    """Pre-Unicode Arabic font whose codes land on Latin-1 and symbol characters."""
    return _remap(text, {ch: chr(0xC0 + i) for i, ch in enumerate(LETTERS)})


def ascii_legacy_encoding(text: str) -> str:
    """Pre-Unicode Arabic font whose glyphs sit on printable ASCII codes."""
    printable = [chr(cp) for cp in range(0x21, 0x7F)]
    _rng(text, "ascii").shuffle(printable)
    return _remap(text, dict(zip(LETTERS, printable, strict=False)))


def quran_glyph_codes(text: str) -> str:
    """King Fahd Complex page fonts: one Presentation Forms-A code point per word."""
    span = 0xFDFF - 0xFB51
    count = 0
    lines = []
    for line in text.splitlines():
        words = []
        for word in line.split(" "):
            if letter_count(word):
                word = chr(0xFB51 + count % span)
                count += 1
            words.append(word)
        lines.append(" ".join(words))
    return "\n".join(lines)


def presentation_forms(text: str) -> str:
    return "\n".join(arabic_reshaper.reshape(line) for line in text.splitlines())


def visual_order(text: str) -> str:
    return "\n".join(line[::-1] for line in text.splitlines())


def mixed_order(text: str) -> str:
    """Reverse every other line that contains Arabic (Marker-style mixed output)."""
    out, flip = [], False
    for line in text.splitlines():
        if letter_count(line):
            line = line[::-1] if flip else line
            flip = not flip
        out.append(line)
    return "\n".join(out)


def lam_alef_transposition(text: str) -> str:
    """pdftotext/Marker fault: 'المحتويات' -> 'املحتويات'."""
    rng = _rng(text, "transpose")

    def fix(word: str) -> str:
        if (
            len(word) >= 4
            and word.startswith("ال")
            and word[2] in ARABIC_LETTERS
            and rng.random() < 0.6
        ):
            return "ا" + word[2] + "ل" + word[3:]
        return word

    return "\n".join(" ".join(fix(w) for w in line.split(" ")) for line in text.splitlines())


def lost_boundaries(text: str) -> str:
    rng = _rng(text, "boundaries")
    out = []
    for word in text.split(" "):
        while len(word) > 3:
            cut = rng.randint(1, 3)
            out.append(word[:cut])
            word = word[cut:]
        out.append(word)
    return " ".join(out)


# (name, corruption, expected reason in scan mode, expected reason in text mode)
# None means "must stay keep"; "-" means the fault is not observable in that mode.
CASES: list[tuple[str, Callable[[str], str], str | None, str | None]] = [
    ("clean", lambda t: t, None, None),
    ("visual order", visual_order, None, "visual_order"),
    (
        "all letters substituted",
        substitute_all,
        "same_script_substitution",
        "same_script_substitution",
    ),
    (
        "6 letters substituted",
        substitute_some,
        "same_script_substitution",
        "same_script_substitution",
    ),
    ("meem insertion", meem_insertion, "same_script_substitution", "same_script_substitution"),
    ("private-use glyphs", private_use, "unmapped_glyphs", "unmapped_glyphs"),
    ("raw CID codes", cid_codes, "unmapped_glyphs", "unmapped_glyphs"),
    ("legacy encoding", legacy_encoding, "legacy_encoding", "legacy_encoding"),
    ("ASCII legacy encoding", ascii_legacy_encoding, "legacy_encoding", "legacy_encoding"),
    ("Quran glyph codes", quran_glyph_codes, "quran_glyph_codes", "quran_glyph_codes"),
    ("presentation forms", presentation_forms, "presentation_forms", "presentation_forms"),
    ("lam-alef transposition", lam_alef_transposition, "-", "lam_alef_transposition"),
    ("lost word boundaries", lost_boundaries, "-", "lost_word_boundaries"),
]


# ---------------------------------------------------------------- calibration


def quantile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, math.ceil(q * len(ordered)) - 1)]


def ceil_to(value: float, step: float) -> float:
    return round(math.ceil(value / step - 1e-9) * step, 4)


def fit(calib_pages: list[str]) -> Thresholds:
    """Fit each threshold to a TARGET_FALSE_FLAG rate on clean calibration windows."""
    models = default_models()
    base = Thresholds()
    smallest = WINDOW_SIZES[0]
    clean = [w for page in calib_pages for w in windows(page, smallest)]
    keep = 1 - TARGET_FALSE_FLAG

    # A spike is a character rarer than 99.9% of characters in clean text.
    letter_surprisals = [s for w in clean for s in models.spaced.surprisals(letters_only(w))]
    spike_bits = ceil_to(quantile(letter_surprisals, 0.999), 0.5)
    probe = Thresholds(spike_bits=spike_bits)

    logical = [measure(w, models, probe) for w in clean]
    visual = [measure(visual_order(w), models, probe) for w in clean]
    both = logical + visual
    return Thresholds(
        min_letters=smallest,
        substitution_bits=ceil_to(quantile([m.bits for m in both], keep), 0.05),
        spike_bits=spike_bits,
        spike_rate=ceil_to(quantile([m.spike_rate for m in both], keep) + 0.005, 0.005),
        # Generous: this only decides between two kinds of failure, never keep vs flag.
        unspaced_bits=ceil_to(quantile([m.bits_unspaced for m in both], keep) + 0.25, 0.05),
        short_token_ratio=ceil_to(
            quantile([m.short_token_ratio for m in logical], keep) + 0.02, 0.01
        ),
        orientation_margin=base.orientation_margin,
        presentation_form_ratio=base.presentation_form_ratio,
        unmapped_ratio=base.unmapped_ratio,
        transposition_ratio=max(
            0.1, ceil_to(quantile([m.transposition_ratio for m in logical], keep) + 0.02, 0.01)
        ),
        mixed_order_min_share=base.mixed_order_min_share,
    )


# ---------------------------------------------------------------- evaluation


def evaluate(test_pages: list[str], t: Thresholds) -> dict:
    models = default_models()
    results: dict = {}
    for size in WINDOW_SIZES:
        rows = {}
        for name, corrupt, expect_scan, expect_text in CASES:
            hits = Counter()
            n = 0
            for page in test_pages:
                for window in windows(page, size):
                    text = corrupt(window)
                    n += 1
                    for mode, expected, order_known in (
                        ("scan", expect_scan, False),
                        ("text", expect_text, True),
                    ):
                        if expected == "-":
                            continue
                        a = assess_text(text, order_known=order_known, models=models, thresholds=t)
                        ok = a.route == "keep" if expected is None else expected in a.reasons
                        hits[mode] += ok
                        hits[f"{mode}_flagged"] += a.route != "keep"
            rows[name] = {
                "windows": n,
                "scan": None if expect_scan == "-" else hits["scan"] / n,
                "text": None if expect_text == "-" else hits["text"] / n,
                "text_flagged": hits["text_flagged"] / n,
                "expect_scan": expect_scan or "keep",
                "expect_text": expect_text or "keep",
            }
        results[size] = rows

    # Mixed reading order is a page-level property: evaluate on whole pages.
    pages = [
        p for p in test_pages if sum(1 for line in p.splitlines() if letter_count(line) >= 20) >= 4
    ]
    mixed_hits = sum(
        "mixed_reading_order" in assess_text(mixed_order(p), models=models, thresholds=t).reasons
        for p in pages
    )
    clean_mixed = sum(
        "mixed_reading_order" in assess_text(p, models=models, thresholds=t).reasons for p in pages
    )
    results["mixed_pages"] = {
        "pages": len(pages),
        "detected": mixed_hits / len(pages) if pages else None,
        "false_flag_on_clean": clean_mixed / len(pages) if pages else None,
    }
    return results


def scan_real(pdfs: list[str], pages: list[int] | None, t: Thresholds) -> list[dict]:
    from harfix.pdf import scan_pdf

    summary = []
    for path in pdfs:
        report = scan_pdf(path, pages=pages, thresholds=t)
        fonts: dict[str, dict] = defaultdict(
            lambda: {"runs": 0, "letters": 0, "bits": [], "routes": Counter()}
        )
        for page in report.pages:
            for font in page.fonts:
                a = font.assessment
                if not a.decisive:
                    continue
                if font.scope == "page":
                    entry = fonts[font.font]
                    entry["letters"] += int(a.metrics.get("arabic_letters", 0))
                    if "bits" in a.metrics:
                        entry["bits"].append(float(a.metrics["bits"]))
                else:
                    # One verdict on the font's short runs pooled across pages: count it once.
                    entry = fonts[f"{font.font} (short runs, pooled)"]
                    entry["letters"] = int(a.metrics.get("arabic_letters", 0))
                    if "bits" in a.metrics:
                        entry["bits"] = [float(a.metrics["bits"])]
                entry["runs"] += 1
                entry["routes"][a.route] += 1
        summary.append(
            {
                "file": _title(Path(path)),
                "pages": len(report.pages),
                "page_routes": report.route_counts,
                "fonts": {
                    name: {
                        "runs": f["runs"],
                        "letters": f["letters"],
                        "median_bits": round(statistics.median(f["bits"]), 2)
                        if f["bits"]
                        else None,
                        "routes": dict(f["routes"]),
                    }
                    for name, f in sorted(fonts.items(), key=lambda kv: -kv[1]["letters"])
                },
            }
        )
    return summary


def _title(path: Path) -> str:
    """Book title from a `fetch_shamela.py` manifest next to the PDF, else the file name."""
    manifest = path.parent / "manifest.jsonl"
    if manifest.is_file():
        for line in manifest.open(encoding="utf-8"):
            book = json.loads(line)
            if book.get("file") == path.name:
                return f"{book['name']} (Shamela {book['book_id']}, {book['category']})"
    return path.name


# ---------------------------------------------------------------- report


def pct(value: float | None) -> str:
    return "n/a" if value is None else f"{100 * value:.1f}%"


def write_report(
    fitted: Thresholds, t: Thresholds, results: dict, real: dict[str, list[dict]], meta: dict
) -> str:
    lines = [
        "# harfix calibration report",
        "",
        f"Generated {meta['date']} by `scripts/calibrate.py`. Model `{meta['model_sha256'][:12]}`.",
        "",
        "Thresholds were fitted on the **calib** split; every rate below is measured on the",
        f"untouched **test** split ({meta['test_pages']} pages). Data: Misraj-DocOCR and",
        "KITAB_pdf_to_markdown_reviewed (Apache-2.0), split by content hash.",
        "",
        "## Thresholds",
        "",
        "`fitted` targets a 0.5% false-flag rate per clean window. `used` raises some values",
        "to `DOMAIN_FLOORS` (see `scripts/calibrate.py`), chosen so clean Egyptian court and",
        "statute PDFs are not flagged.",
        "",
        "| Name | Fitted | Used |",
        "|---|---:|---:|",
        *[f"| `{k}` | {fitted.__dict__[k]} | {v} |" for k, v in t.__dict__.items()],
        "",
        "## Detection on the test split",
        "",
        "`scan` = PDF text-layer mode (character order unknown). `text` = extractor-output mode.",
        "For `clean` and `visual order` in scan mode the rate is the share left as `keep`.",
        "`text: any flag` is the share routed anywhere but `keep`, whatever the reason.",
        "",
    ]
    for size in WINDOW_SIZES:
        lines += [
            f"### Windows of ≥{size} Arabic letters",
            "",
            "| Case | Windows | Expected (scan) | scan | Expected (text) | text | text: any flag |",
            "|---|---:|---|---:|---|---:|---:|",
        ]
        for name, row in results[size].items():
            lines.append(
                f"| {name} | {row['windows']} | {row['expect_scan']} | {pct(row['scan'])} | "
                f"{row['expect_text']} | {pct(row['text'])} | {pct(row['text_flagged'])} |"
            )
        lines.append("")
    mixed = results["mixed_pages"]
    lines += [
        "### Mixed reading order (whole pages)",
        "",
        f"Alternate lines reversed on {mixed['pages']} test pages: "
        f"detected {pct(mixed['detected'])}; false `mixed_reading_order` flags on the same",
        f"pages unmodified: {pct(mixed['false_flag_on_clean'])}.",
        "",
    ]
    for label, docs in real.items():
        if not docs:
            continue
        intro = (
            "Used to choose `DOMAIN_FLOORS`, so these are not an independent measurement."
            if label == "dev"
            else "Not used for any threshold."
        )
        lines += [
            f"## Real PDFs ({label})",
            "",
            f"{intro} Per-font summary of runs with enough Arabic text to judge.",
            "",
        ]
        for doc in docs:
            routes = ", ".join(f"{k}={v}" for k, v in doc["page_routes"].items() if v)
            lines += [
                f"### {doc['file']}",
                "",
                f"{doc['pages']} pages scanned; page routes: {routes}.",
                "",
            ]
            lines += [
                "| Font | Runs | Letters | Median bits/char | Routes |",
                "|---|---:|---:|---:|---|",
            ]
            for name, f in doc["fonts"].items():
                r = ", ".join(f"{k}={v}" for k, v in f["routes"].items())
                lines.append(
                    f"| {name} | {f['runs']} | {f['letters']} | {f['median_bits']} | {r} |"
                )
            lines.append("")
    lines += [
        "## Limitations",
        "",
        "- Corruptions are synthetic except for the real-PDF sections; real fonts can fail in",
        "  patterns not simulated here. The real-PDF tables have no ground-truth labels.",
        "- `DOMAIN_FLOORS` trade recall for precision: partial substitutions (a few swapped",
        "  letters) and light padding are caught only part of the time.",
        "- The model is trained on about 300 pages of modern standard Arabic. Classical or",
        "  dialectal text scores higher and needs its own calibration before relying on it.",
        "- Runs shorter than `min_letters` are judged by pooling the font's short runs across",
        "  the scanned pages; spike rates are only used from `spike_min_letters` up.",
        "- Real PDFs are only those with a text layer the scan can judge; scanned books are",
        "  routed to `ocr` as `no_text_layer` and say nothing about detection accuracy.",
        "",
    ]
    return "\n".join(lines)


def apply_floors(fitted: Thresholds) -> Thresholds:
    values = dict(fitted.__dict__)
    for name, floor in DOMAIN_FLOORS.items():
        values[name] = max(values[name], floor)
    return Thresholds(**values)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dev-pdf", nargs="*", default=[], help="PDFs used to set DOMAIN_FLOORS")
    parser.add_argument("--pdf", nargs="*", default=[], help="held-out PDFs to summarize")
    parser.add_argument("--pages", help="1-based pages to scan in each PDF, e.g. 1-30")
    args = parser.parse_args()

    records = [json.loads(line) for line in (ROOT / "build" / "pages.jsonl").open(encoding="utf-8")]
    calib = [r["text"] for r in records if r["split"] == "calib"]
    test = [r["text"] for r in records if r["split"] == "test"]

    fitted = fit(calib)
    t = apply_floors(fitted)
    results = evaluate(test, t)

    pages = None
    if args.pages:
        from harfix.cli import _parse_pages

        pages = _parse_pages(args.pages)
    real = {
        "dev": scan_real(args.dev_pdf, pages, t),
        "held-out": scan_real(args.pdf, pages, t),
    }

    model_path = ROOT / "src" / "harfix" / "data" / "arabic_char_lm.json.gz"
    meta = {
        "date": dt.date.today().isoformat(),
        "model_sha256": hashlib.sha256(model_path.read_bytes()).hexdigest(),
        "calib_pages": len(calib),
        "test_pages": len(test),
        "target_false_flag": TARGET_FALSE_FLAG,
    }
    (ROOT / "src" / "harfix" / "data" / "thresholds.json").write_text(
        json.dumps({"thresholds": t.__dict__, "calibration": meta}, indent=2) + "\n",
        encoding="utf-8",
    )
    report = write_report(fitted, t, results, real, meta)
    (ROOT / "reports").mkdir(exist_ok=True)
    (ROOT / "reports" / "calibration.md").write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
