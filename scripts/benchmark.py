"""Measure `harfix scan` against labels derived from Shamela's typed text.

Usage:
    uv run python scripts/benchmark.py fetch-text   # typed text from shamela.ws, resumable
    uv run python scripts/benchmark.py run          # label, scan, score
    uv run python scripts/benchmark.py repair       # search matches before/after repair
    uv run --group extractors python scripts/benchmark.py extractors  # `check` per extractor
    uv run python scripts/benchmark.py decode       # `harfix decode` on the labelled pages

Shamela's typed text of a book is a transcription of the same printed edition as the PDF it
links. A PDF font run made of real words has the right letters; a run that is not has a
broken text layer. No OCR, no hand labels and no harfix detection code are involved:

- The vocabulary is every word of every fetched transcription, plus an English word list
  for abstracts and references. Using all books rather than only the PDF's own keeps PDF
  content Shamela did not transcribe (other articles in a journal issue, publisher pages)
  from being labelled broken.
- Arabic words are compared after `letters_only` and folding of alef, yeh and teh marbuta
  variants, in either reading direction. A lone letter only counts as a word if it is
  the conjunction و, so text layers that shatter words into letters do not pass. Other
  words without Arabic letters (Latin, symbols) are looked up as they are. Words holding
  unmapped glyphs (U+FFFD, private use, raw CID codes) are never found.
- A run with at least MIN_WORDS such words is labelled `clean` when at least CLEAN_SHARE
  of them are found, `broken` when at most BROKEN_SHARE are, and `partial` in between.
- A page is `broken` if any labelled run on it is broken, `clean` if every labelled run is
  clean, and otherwise `partial`. A flagged page whose flagging runs are all too short to
  label is `unverified`; pages without labelled runs are `unlabelled`.

`fetch-text` reads each book page by page from the public page API that shamela.ws's own
reader uses, two requests at most in flight with a pause, and caches every book as JSON
lines.
The PDFs and texts are third-party works: everything stays under corpus/, never commit it.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import re
import shutil
import statistics
import subprocess
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from pdfminer.high_level import extract_pages
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfparser import PDFParser

from harfix import ROUTES, HarfixError, repair_text, scan_pdf
from harfix.normalize import letters_only
from harfix.pdf import _collect_page

ROOT = Path(__file__).resolve().parent.parent
PAGE_API = "https://shamela.ws/ajax/pageContent/{book}/{page}"
PAUSE = 0.25  # seconds between requests
PAGES_PER_BOOK = 40
MIN_WORDS = 8
CLEAN_SHARE = 0.75
BROKEN_SHARE = 0.35
FLAGGED = ("reextract", "ocr")  # routes that say the letters cannot be used as they are

_FOLD = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ى": "ي", "ة": "ه", "ؤ": "و", "ئ": "ي"})
_ARABIC = re.compile(r"[\u0600-\u06FF\uFB50-\uFDFF\uFE70-\uFEFF]")
_EDGES = ".,;:!?()[]{}\"'«»-–—/*،؛؟…"
_TAGS = re.compile(r"<[^>]+>")
_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


# ---------------------------------------------------------------- typed text


def _page(book: str, page: str) -> dict:
    request = urllib.request.Request(
        PAGE_API.format(book=book, page=page), headers={"User-Agent": "harfix-benchmark/0.1"}
    )
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.load(response)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            if attempt == 3:
                raise
            time.sleep(5 * (attempt + 1))
    raise AssertionError("unreachable")


def _fetch_book(book: str, target: Path) -> None:
    lines, page = [], "1"
    while page and page != "None":
        data = _page(book, page)
        text = html.unescape(_TAGS.sub(" ", data.get("nass") or ""))
        record = {
            "page": data["pageId"],
            # Printed page number and volume of the edition, when Shamela has them.
            "printed": data.get("pageNum"),
            "part": data.get("part") or None,
            "text": text,
        }
        lines.append(json.dumps(record, ensure_ascii=False))
        page = data.get("nextId")
        time.sleep(PAUSE)
    partial = target.with_suffix(".part")
    partial.write_text("\n".join(lines) + "\n", encoding="utf-8")
    partial.rename(target)
    print(f"{book}: {len(lines)} pages", flush=True)


def fetch_text(manifest: Path) -> None:
    """Follow each book's page chain from its first page; skip books already cached."""
    out = manifest.parent / "text"
    out.mkdir(exist_ok=True)
    # Single-book PDFs first: collected works need every book they hold before they count.
    wanted = sorted({(len(pdf["book_ids"]), i) for pdf in _pdfs(manifest) for i in pdf["book_ids"]})
    todo = [str(book) for _, book in wanted if not (out / f"{book}.jsonl").exists()]
    with ThreadPoolExecutor(2) as pool:  # at most two requests in flight
        for future in [pool.submit(_fetch_book, b, out / f"{b}.jsonl") for b in todo]:
            future.result()


# ---------------------------------------------------------------- labels


# Glyphs with no Unicode mapping: a word containing one has lost letters, whatever else
# it contains. U+F000-U+F0FF is where Symbol and ornament fonts (bullets, AGA Arabesque
# borders) put their glyphs on purpose, so those are ignored rather than counted.
_UNMAPPED = re.compile(r"[\ufffd\ue000-\uefff\uf100-\uf8ff]|\(cid:\d+\)")
_SYMBOL_FONT = re.compile(r"[\uf000-\uf0ff]")


def _words(text: str) -> tuple[list[str], list[str], int]:
    """(Arabic words, other words, words with unmapped glyphs) of extracted text."""
    arabic, other, unmapped = [], [], 0
    for raw in _SYMBOL_FONT.sub(" ", text.translate(_DIGITS)).split():
        if _UNMAPPED.search(raw):
            unmapped += 1
        elif _ARABIC.search(raw):
            arabic += [w.translate(_FOLD) for w in letters_only(raw).split()]
        else:
            word = raw.strip(_EDGES).lower()
            if len(word) >= 3 and not word.isdigit():
                other.append(word)
    return arabic, other, unmapped


def vocabulary(typed: str, words_file: Path | None) -> set[str]:
    """Words of the typed transcriptions, plus an English word list for abstracts and
    references that the transcriptions leave out."""
    arabic, other, _ = _words(typed)
    vocab = {w for w in arabic if len(w) >= 2} | set(other)
    if words_file is not None:
        vocab |= {line.strip().lower() for line in words_file.open(encoding="utf-8")}
    return vocab


def _found(word: str, vocab: set[str]) -> bool:
    # A lone letter is a word only for the conjunction و; text layers that shatter words
    # into single letters must not pass because those letters are common.
    if len(word) == 1:
        return word == "و"
    return word in vocab or word[::-1] in vocab


def label_run(text: str, vocab: set[str]) -> tuple[str, int, float]:
    """(label, counted words, share found in the vocabulary)."""
    arabic, other, unmapped = _words(text)
    found = sum(1 for w in arabic if _found(w, vocab))
    found += sum(1 for w in other if w in vocab)
    total = len(arabic) + len(other) + unmapped
    if total < MIN_WORDS:
        return "unlabelled", total, 0.0
    share = found / total
    if share >= CLEAN_SHARE:
        return "clean", total, share
    if share <= BROKEN_SHARE:
        return "broken", total, share
    return "partial", total, share


def page_label(fonts: list[dict], route: str) -> str:
    labelled = [f for f in fonts if f["label"] != "unlabelled"]
    if not labelled:
        return "unlabelled"
    flagging = [f for f in fonts if f["route"] in FLAGGED]
    if route in FLAGGED and all(f["label"] == "unlabelled" for f in flagging):
        return "unverified"
    labels = [f["label"] for f in labelled]
    if "broken" in labels:
        return "broken"
    return "clean" if all(x == "clean" for x in labels) else "partial"


# ---------------------------------------------------------------- scoring


def _page_count(path: Path) -> int:
    with path.open("rb") as fh:
        return sum(1 for _ in PDFPage.create_pages(PDFDocument(PDFParser(fh))))


def sample_pages(count: int) -> list[int]:
    if count <= PAGES_PER_BOOK:
        return list(range(1, count + 1))
    step = count / PAGES_PER_BOOK
    return sorted({int(i * step) + 1 for i in range(PAGES_PER_BOOK)})


def evaluate_book(pdf: Path, vocab: set[str]) -> dict:
    pages = sample_pages(_page_count(pdf))
    report = scan_pdf(pdf, pages=pages)
    texts = [
        _collect_page(layout)[0]
        for layout in extract_pages(str(pdf), page_numbers=[p - 1 for p in pages])
    ]
    rows = []
    for page, runs in zip(report.pages, texts, strict=True):
        fonts = []
        for font in page.fonts:
            label, words, share = label_run(runs.get(font.font, ""), vocab)
            fonts.append(
                {
                    "font": font.font,
                    "scope": font.scope,
                    "route": font.assessment.route,
                    "reasons": font.assessment.reasons,
                    "label": label,
                    "words": words,
                    "found": round(share, 3),
                    "sample": runs.get(font.font, "")[:160],
                }
            )
        rows.append(
            {
                "page": page.page,
                "route": page.route,
                "reasons": page.reasons,
                "label": page_label(fonts, page.route),
                "fonts": fonts,
            }
        )
    return {"pages": rows}


def confusion(pairs: list[tuple[str, str]]) -> dict:
    """pairs of (label, route) restricted to clean/broken labels."""
    c = Counter()
    for label, route in pairs:
        if label in ("clean", "broken"):
            c[(label, route in FLAGGED)] += 1
    tp, fp = c[("broken", True)], c[("clean", True)]
    fn, tn = c[("broken", False)], c[("clean", False)]
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": tp / (tp + fp) if tp + fp else None,
        "recall": tp / (tp + fn) if tp + fn else None,
    }


def pct(x: float | None) -> str:
    return "n/a" if x is None else f"{100 * x:.1f}%"


def write_report(results: list[dict], skipped: list[str]) -> str:
    page_pairs = [(p["label"], p["route"]) for r in results for p in r["pages"]]
    font_pairs = [(f["label"], f["route"]) for r in results for p in r["pages"] for f in p["fonts"]]
    page_labels = Counter(label for label, _ in page_pairs)
    font_labels = Counter(label for label, _ in font_pairs if label != "unlabelled")

    by_reason: dict[str, Counter] = defaultdict(Counter)
    for r in results:
        for p in r["pages"]:
            for f in p["fonts"]:
                if f["route"] != "keep" and f["label"] != "unlabelled":
                    for reason in f["reasons"]:
                        by_reason[reason][f["label"]] += 1

    lines = [
        "# harfix benchmark: Shamela books",
        "",
        f"Generated {dt.date.today().isoformat()} by `scripts/benchmark.py`.",
        "",
        "Labels come from typed text, not from harfix: a font run is `clean` when at least",
        f"{CLEAN_SHARE:.0%} of its words occur in Shamela's transcriptions of the books (or in",
        f"an English word list), `broken` at {BROKEN_SHARE:.0%} or less, `partial` in between;",
        f"runs with fewer than {MIN_WORDS} countable words are unlabelled. Words containing",
        "unmapped glyphs count as not found. See the script docstring for details.",
        "",
        "A harfix verdict counts as a flag when the route is `reextract` or `ocr`; `repair`",
        "means the letters are right, so it counts with `keep`. A flagged page whose flagging",
        "runs are all too short to label is `unverified` and left out of the page scores.",
        "",
        f"Books: {len(results)} with a PDF text layer and a typed text"
        + (f" ({len(skipped)} skipped: {', '.join(skipped)})" if skipped else "")
        + f". Up to {PAGES_PER_BOOK} pages per book, evenly spaced.",
        "",
        "## Labels",
        "",
        "| Unit | clean | broken | partial | unverified | unlabelled |",
        "|---|---:|---:|---:|---:|---:|",
        f"| pages | {page_labels['clean']} | {page_labels['broken']} | "
        f"{page_labels['partial']} | {page_labels['unverified']} | {page_labels['unlabelled']} |",
        f"| font runs | {font_labels['clean']} | {font_labels['broken']} | "
        f"{font_labels['partial']} | - | - |",
        "",
        "## harfix against the labels (clean and broken only)",
        "",
        "Books are split by a hash of the PDF into `dev` (used when changing harfix rules) and",
        "`test` (not looked at when changing rules). `all` is both.",
        "",
        "| Split | Unit | Flagged broken | Flagged clean | Missed broken | Kept clean | "
        "Precision | Recall |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for split in ("dev", "test", "all"):
        chosen = [r for r in results if split in ("all", r["split"])]
        for name, m in (
            ("pages", confusion([(p["label"], p["route"]) for r in chosen for p in r["pages"]])),
            (
                "font runs",
                confusion(
                    [
                        (f["label"], f["route"])
                        for r in chosen
                        for p in r["pages"]
                        for f in p["fonts"]
                    ]
                ),
            ),
        ):
            lines.append(
                f"| {split} | {name} | {m['tp']} | {m['fp']} | {m['fn']} | {m['tn']} | "
                f"{pct(m['precision'])} | {pct(m['recall'])} |"
            )
    lines += [
        "",
        "## Flagged font runs by reason",
        "",
        "| Reason | clean | broken | partial |",
        "|---|---:|---:|---:|",
        *[
            f"| `{reason}` | {c['clean']} | {c['broken']} | {c['partial']} |"
            for reason, c in sorted(by_reason.items())
        ],
        "",
        "## Per book",
        "",
        "| Shamela id | Split | Pages | Labels (clean/broken/partial/unverified/unlabelled) | "
        "Flagged | Precision | Recall |",
        "|---:|---|---:|---|---:|---:|---:|",
    ]
    for r in results:
        labels = Counter(p["label"] for p in r["pages"])
        m = confusion([(p["label"], p["route"]) for p in r["pages"]])
        flagged = sum(1 for p in r["pages"] if p["route"] in FLAGGED)
        lines.append(
            f"| {r['book_id']} | {r['split']} | {len(r['pages'])} | "
            f"{labels['clean']}/{labels['broken']}/"
            f"{labels['partial']}/{labels['unverified']}/{labels['unlabelled']} | {flagged} | "
            f"{pct(m['precision'])} | {pct(m['recall'])} |"
        )
    lines += [
        "",
        "## Limitations",
        "",
        "- Labels test whether the extracted words exist, not their order or position: a run",
        "  with correct words in a broken order is labelled clean.",
        "- A garbled word occasionally matches a real one, so badly broken runs still find",
        "  about 10-15% of their words; partial labels are left out of precision and recall.",
        "- Book titles are omitted: see the local manifest for names and sources.",
        "",
    ]
    return "\n".join(lines)


def split_of(book: dict) -> str:
    """Stable dev/test assignment from the PDF's content hash."""
    bucket = int(hashlib.sha256(book["sha256"].encode()).hexdigest()[:8], 16)
    return "dev" if bucket % 2 == 0 else "test"


def _books(manifest: Path) -> list[dict]:
    return [json.loads(line) for line in manifest.open(encoding="utf-8")]


def _pdfs(manifest: Path) -> list[dict]:
    """One entry per distinct PDF with a text layer. Collected works (one PDF holding several
    Shamela books) are judged against the typed text of every book printed in it."""
    groups: dict[str, dict] = {}
    for book in _books(manifest):
        if book.get("text_layer", True):
            groups.setdefault(
                book["sha256"],
                {"file": book["file"], "book_ids": book["pdf_books"], "split": split_of(book)},
            )
    return list(groups.values())


def run(manifest: Path, words_file: Path | None) -> None:
    texts = sorted((manifest.parent / "text").glob("*.jsonl"))
    typed = "\n".join(json.loads(line)["text"] for p in texts for line in p.open(encoding="utf-8"))
    vocab = vocabulary(typed, words_file)
    results, skipped = [], []
    for pdf in _pdfs(manifest):
        key = "+".join(str(i) for i in pdf["book_ids"])
        if not all((manifest.parent / "text" / f"{i}.jsonl").exists() for i in pdf["book_ids"]):
            skipped.append(key)
            continue
        try:
            result = evaluate_book(manifest.parent / pdf["file"], vocab)
        except HarfixError as error:
            print(f"{key}: {error}")
            skipped.append(key)
            continue
        results.append({"book_id": key, "split": pdf["split"], **result})
        print(f"{key}: {len(result['pages'])} pages")

    (manifest.parent / "benchmark_runs.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    report = write_report(results, skipped)
    (ROOT / "reports").mkdir(exist_ok=True)
    (ROOT / "reports" / "benchmark.md").write_text(report, encoding="utf-8")
    print(report)


# ---------------------------------------------------------------- repair

_TASHKEEL = re.compile(r"[\u064B-\u0652\u0670\u0640]")


def _search_tokens(text: str) -> list[str]:
    """Arabic tokens as a plain search index sees them: only diacritics and tatweel go."""
    tokens = (_TASHKEEL.sub("", raw.strip(_EDGES)) for raw in text.split())
    return [t for t in tokens if len(t) >= 2 and _ARABIC.search(t)]


def _extractors() -> dict[str, callable]:
    from pdfminer.high_level import extract_text

    extractors = {"pdfminer.six": lambda pdf: extract_text(str(pdf), maxpages=PAGES_PER_BOOK)}
    if shutil.which("pdftotext"):
        extractors["pdftotext"] = lambda pdf: (
            subprocess.run(
                ["pdftotext", "-l", str(PAGES_PER_BOOK), str(pdf), "-"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout
        )
    if "docling-parse" in _page_extractors():
        extractors["docling-parse"] = lambda pdf: "\f".join(
            _docling_pages(pdf, list(range(1, min(PAGES_PER_BOOK, _page_count(pdf)) + 1)))
        )
    return extractors


def measure_repair(manifest: Path) -> None:
    """Share of words a plain search index would match in the transcriptions, before and
    after `repair_text`, on every page the repair changed."""
    texts = sorted((manifest.parent / "text").glob("*.jsonl"))
    vocab = {
        token
        for p in texts
        for line in p.open(encoding="utf-8")
        for token in _search_tokens(json.loads(line)["text"])
    }

    def share(text: str) -> tuple[float, int] | None:
        """(share of Arabic words found, how many were found)."""
        tokens = _search_tokens(text)
        found = sum(t in vocab for t in tokens)
        return (found / len(tokens), found) if tokens else None

    lines = [
        "# harfix repair: Shamela books",
        "",
        f"Generated {dt.date.today().isoformat()} by `scripts/benchmark.py repair`.",
        "",
        "Each PDF's first pages are extracted, passed through `repair_text`, and every page it",
        "changed is scored before and after: the share of its Arabic words (diacritics and",
        "tatweel removed, nothing else normalized, as a plain search index would see them)",
        "that occur in Shamela's typed transcriptions. A page is worse when that share drops",
        "by more than a point without more words found (spelling out glyph names adds words",
        "that the share before did not count).",
        "",
        "| Extractor | Pages repaired | Reasons | Median share before | Median share after "
        "| Pages worse |",
        "|---|---:|---|---:|---:|---:|",
    ]
    for name, extract in _extractors().items():
        before_after, reasons = [], Counter()
        for pdf in _pdfs(manifest):
            text = extract(manifest.parent / pdf["file"])
            result = repair_text(text)
            reasons.update(c.reason for c in result.changes)
            old, new = text.split("\f"), result.text.split("\f")
            for page in sorted({c.page for c in result.changes}):
                b, a = share(old[page - 1]), share(new[page - 1])
                if b is not None and a is not None:
                    before_after.append((b, a))
        worse = sum(1 for b, a in before_after if a[0] < b[0] - 0.01 and a[1] <= b[1])
        lines.append(
            f"| {name} | {len(before_after)} | "
            + ", ".join(f"`{r}` {n}" for r, n in reasons.most_common())
            + f" | {pct(statistics.median(b[0] for b, _ in before_after))} | "
            f"{pct(statistics.median(a[0] for _, a in before_after))} | {worse} |"
        )
        print(lines[-1])
    lines.append("")
    (ROOT / "reports" / "repair.md").write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------- extractors


def _docling_pages(pdf: Path, pages: list[int]) -> list[str]:
    """Each page's visible text cells, one per line, as docling-parse gives them to Docling."""
    from docling_parse.pdf_parser import DoclingPdfParser

    doc = DoclingPdfParser().load(str(pdf))
    hidden = ("INVISIBLE", "ONLY_CLIPPING")
    out = []
    for n in pages:
        cells = doc.get_page(n).textline_cells
        out.append("\n".join(c.text for c in cells if c.rendering_mode.name not in hidden))
    doc.unload()
    return out


def _pdftotext_pages(pdf: Path, pages: list[int]) -> list[str]:
    return [
        subprocess.run(
            ["pdftotext", "-f", str(n), "-l", str(n), str(pdf), "-"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip("\f")
        for n in pages
    ]


def _pdfminer_pages(pdf: Path, pages: list[int]) -> list[str]:
    from pdfminer.high_level import extract_text

    # extract_text ends every page with a form feed.
    return [extract_text(str(pdf), page_numbers=[n - 1]).strip("\f") for n in pages]


def _page_extractors() -> dict[str, callable]:
    extractors = {"pdfminer.six": _pdfminer_pages}
    if shutil.which("pdftotext"):
        extractors["pdftotext"] = _pdftotext_pages
    try:
        import docling_parse  # noqa: F401

        extractors["docling-parse"] = _docling_pages
    except ImportError:
        print("docling-parse not installed: uv run --group extractors ...")
    return extractors


def _check_book(job: tuple[str, Path, list[int]]) -> list[tuple[str, list[str], str]]:
    """(route, reasons, repaired text) per page, as `harfix check` and `repair` see the
    extractor's output with one form feed between pages."""
    from harfix import assess_document

    name, pdf, pages = job
    texts = _page_extractors()[name](pdf, pages)
    joined = "\f".join(texts)
    report = assess_document(joined)
    repaired = repair_text(joined).text.split("\f")
    by_page: dict[int, list] = defaultdict(list)
    for segment in report.segments:
        by_page[segment.page].append(segment.assessment)
    out = []
    for i in range(len(pages)):
        found = by_page.get(i + 1, [])
        route = max((a.route for a in found), default="keep", key=ROUTES.index)
        reasons = sorted({r for a in found for r in a.reasons})
        out.append((route, reasons, repaired[i]))
    return out


def measure_extractors(manifest: Path, words_file: Path | None) -> None:
    """`harfix check` on each extractor's output of the labelled pages of `run`.

    Page labels come from `run` (the PDF's font runs against the typed text), so they say
    whether the text layer is broken whatever the extractor. A broken page is caught when
    `check` routes it to `ocr`, or to `repair` and the repaired text then labels clean. A
    clean page is wrongly flagged when it is routed to `ocr`. `reextract` (the extractor
    damaged correct text) is counted on its own.
    """
    from concurrent.futures import ProcessPoolExecutor

    results = json.loads((manifest.parent / "benchmark_runs.json").read_text(encoding="utf-8"))
    texts = sorted((manifest.parent / "text").glob("*.jsonl"))
    typed = "\n".join(json.loads(line)["text"] for p in texts for line in p.open(encoding="utf-8"))
    vocab = vocabulary(typed, words_file)
    files = {"+".join(str(i) for i in pdf["book_ids"]): pdf["file"] for pdf in _pdfs(manifest)}

    lines = [
        "# harfix check: one benchmark, three extractors",
        "",
        f"Generated {dt.date.today().isoformat()} by `scripts/benchmark.py extractors`.",
        "",
        "The labelled pages of [`benchmark.md`](benchmark.md), extracted by each tool and passed",
        "to `harfix check` and `harfix repair` with one form feed between pages. Labels say",
        "whether the PDF's text layer is broken and do not depend on the extractor. A broken",
        "page is caught when it is routed to `ocr`, or to `repair` and the repaired text then",
        "labels clean; a clean page is wrongly flagged when it is routed to `ocr`. `reextract`",
        "means the extractor damaged text that is right in the PDF; it is counted separately.",
        "docling-parse text is each page's visible text cells, one per line, as Docling",
        "receives it.",
        "",
        "| Split | Extractor | Broken: ocr | Broken: repaired | Broken: reextract | "
        "Broken: missed | Clean: ocr | Clean: reextract | Clean: kept or repaired | "
        "Precision | Recall |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    caught_reasons, missed_reasons = {}, {}
    for name in _page_extractors():
        jobs = [
            (name, manifest.parent / files[r["book_id"]], [p["page"] for p in r["pages"]])
            for r in results
        ]
        with ProcessPoolExecutor() as pool:
            checked = list(pool.map(_check_book, jobs))
        rows = []
        for r, pages in zip(results, checked, strict=True):
            for p, (route, reasons, repaired) in zip(r["pages"], pages, strict=True):
                if p["label"] not in ("clean", "broken"):
                    continue
                if route in ("ocr", "reextract"):
                    verdict = route
                elif route == "repair" and label_run(repaired, vocab)[0] == "clean":
                    verdict = "repaired"
                else:
                    verdict = "kept"
                rows.append((r["split"], p["label"], verdict, reasons))
        caught_reasons[name] = Counter(
            reason
            for _, label, verdict, reasons in rows
            if label == "broken" and verdict in ("ocr", "repaired")
            for reason in reasons
        )
        missed_reasons[name] = Counter(
            ", ".join(reasons) or "none"
            for _, label, verdict, reasons in rows
            if label == "broken" and verdict == "kept"
        )
        for split in ("test", "all"):
            c = Counter((label, verdict) for s, label, verdict, _ in rows if split in ("all", s))
            caught = c["broken", "ocr"] + c["broken", "repaired"]
            broken = sum(n for (label, _), n in c.items() if label == "broken")
            wrong = c["clean", "ocr"]
            lines.append(
                f"| {split} | {name} | {c['broken', 'ocr']} | {c['broken', 'repaired']} | "
                f"{c['broken', 'reextract']} | {c['broken', 'kept']} | {wrong} | "
                f"{c['clean', 'reextract']} | {c['clean', 'kept'] + c['clean', 'repaired']} | "
                f"{pct(caught / (caught + wrong) if caught + wrong else None)} | "
                f"{pct(caught / broken if broken else None)} |"
            )
            print(lines[-1])
    lines += ["", "Reasons on caught broken pages (all books):", ""]
    for name, reasons in caught_reasons.items():
        lines.append(f"- {name}: " + ", ".join(f"`{r}` {n}" for r, n in reasons.most_common()))
    lines += ["", "Missed broken pages by reasons found (all books):", ""]
    for name, reasons in missed_reasons.items():
        lines.append(f"- {name}: " + ", ".join(f"{r} {n}" for r, n in reasons.most_common(6)))
        print(lines[-1])
    lines.append("")
    (ROOT / "reports" / "extractors.md").write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------- decode


def _decode_book(job: tuple[Path, list[int]]) -> list[tuple[int, bool, bool, str]]:
    from harfix import decode_pdf

    pdf, pages = job
    return [
        (p.page, p.assessment is not None, p.trusted, p.text) for p in decode_pdf(pdf, pages=pages)
    ]


def measure_decode(manifest: Path, words_file: Path | None) -> None:
    """`harfix decode` on the labelled pages of `run`: which pages it decodes, which it
    trusts, and whether the decoded text then labels clean against the typed text."""
    from concurrent.futures import ProcessPoolExecutor

    results = json.loads((manifest.parent / "benchmark_runs.json").read_text(encoding="utf-8"))
    texts = sorted((manifest.parent / "text").glob("*.jsonl"))
    typed = "\n".join(json.loads(line)["text"] for p in texts for line in p.open(encoding="utf-8"))
    vocab = vocabulary(typed, words_file)
    files = {"+".join(str(i) for i in pdf["book_ids"]): pdf["file"] for pdf in _pdfs(manifest)}
    labelled = [(r, [p for p in r["pages"] if p["label"] in ("clean", "broken")]) for r in results]
    jobs = [(manifest.parent / files[r["book_id"]], [p["page"] for p in ps]) for r, ps in labelled]
    with ProcessPoolExecutor() as pool:
        decoded = list(pool.map(_decode_book, jobs))
    table: Counter = Counter()
    by_book: dict[str, list[str]] = defaultdict(list)
    for (r, pages), out in zip(labelled, decoded, strict=True):
        labels = {p["page"]: p["label"] for p in pages}
        for page, was_decoded, trusted, text in out:
            if not was_decoded:
                table[labels[page], "not decoded"] += 1
                continue
            after = label_run(text, vocab)[0]
            table[labels[page], "trusted" if trusted else "not trusted", after] += 1
            by_book[r["book_id"]].append(f"{'trusted' if trusted else 'not trusted'}: {after}")
    lines = [
        "| Page label | Decoded and trusted | of which label clean after decoding | "
        "Decoded, not trusted | Not decoded |",
        "|---|---:|---:|---:|---:|",
    ]
    for label in ("broken", "clean"):
        trusted = sum(n for k, n in table.items() if k[0] == label and k[1] == "trusted")
        untrusted = sum(n for k, n in table.items() if k[0] == label and k[1] == "not trusted")
        lines.append(
            f"| {label} | {trusted} | {table[label, 'trusted', 'clean']} | {untrusted} | "
            f"{table[label, 'not decoded']} |"
        )
    lines += ["", "| Book | Decoded pages | Trusted | Trusted and clean after decoding |"]
    lines.append("|---|---:|---:|---:|")
    for book, verdicts in sorted(by_book.items(), key=lambda kv: int(kv[0].split("+")[0])):
        trusted = [v for v in verdicts if v.startswith("trusted")]
        clean = sum(v == "trusted: clean" for v in verdicts)
        lines.append(f"| {book} | {len(verdicts)} | {len(trusted)} | {clean} |")
    print("\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["fetch-text", "run", "repair", "extractors", "decode"])
    parser.add_argument(
        "--manifest", type=Path, default=ROOT / "corpus" / "shamela_text" / "manifest.jsonl"
    )
    parser.add_argument(
        "--words",
        type=Path,
        default=Path("/usr/share/dict/words"),
        help="English word list (one per line); pass a missing path to skip it",
    )
    args = parser.parse_args()
    if args.command == "fetch-text":
        fetch_text(args.manifest)
    elif args.command == "repair":
        measure_repair(args.manifest)
    elif args.command == "extractors":
        measure_extractors(args.manifest, args.words if args.words.is_file() else None)
    elif args.command == "decode":
        measure_decode(args.manifest, args.words if args.words.is_file() else None)
    else:
        run(args.manifest, args.words if args.words.is_file() else None)


if __name__ == "__main__":
    main()
