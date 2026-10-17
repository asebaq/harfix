"""Download a seeded sample of book PDFs listed in a local al-Maktaba al-Shamela install.

The Shamela desktop app keeps its catalogue in `database/master.db`; about 1,200 books link
a printed-edition PDF hosted on archive.org. This picks a fixed number per subject category
(so grammar, poetry, hadith and tafsir are all represented), downloads them, and writes a
`manifest.jsonl` with the URL, SHA-256 and whether the PDF has a text layer at all. With
`--text-only`, image-only scans are deleted after the check.

The PDFs are third-party works: keep them local, never commit or redistribute them.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sqlite3
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from pdfminer.high_level import extract_pages
from pdfminer.layout import LTChar, LTContainer

DEFAULT_DB = Path.home() / "Library/Application Support/Shamela/database/master.db"


def candidates(db: Path, max_bytes: int) -> dict[str, list[dict]]:
    """Books whose single PDF is on archive.org, grouped by category name.

    `pdf_books` lists every catalogue book printed in the same PDF (collected works hold
    several), so a benchmark can compare the PDF with all of their typed texts.
    """
    query = """
        select b.book_id, b.book_name, c.category_name, b.pdf_links
        from book b join category c on c.category_id = b.book_category
        where b.pdf_links like '%archive.org%'
        order by b.book_id
    """
    books, by_url = [], {}
    with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as conn:
        for book_id, name, category, links in conn.execute(query):
            info = json.loads(links)
            files = info.get("files", [])
            if len(files) != 1 or not files[0].startswith("https://archive.org/"):
                continue
            by_url.setdefault(files[0], []).append(book_id)
            if 0 < info.get("size", 0) <= max_bytes:
                books.append(
                    {"book_id": book_id, "name": name, "category": category, "url": files[0]}
                )
    by_category: dict[str, list[dict]] = {}
    for book in books:
        book["pdf_books"] = by_url[book["url"]]
        by_category.setdefault(book["category"], []).append(book)
    return by_category


def download(url: str, target: Path) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "harfix-corpus/0.1"})
    digest = hashlib.sha256()
    partial = target.with_suffix(".part")
    with urllib.request.urlopen(request, timeout=120) as response, partial.open("wb") as fh:
        while chunk := response.read(1 << 16):
            digest.update(chunk)
            fh.write(chunk)
    partial.rename(target)
    return digest.hexdigest()


def has_text_layer(path: Path, pages: int = 20) -> bool:
    """True if any of the first `pages` pages draws at least one non-space character."""

    def chars(container: LTContainer) -> bool:
        for item in container:
            if isinstance(item, LTChar) and item.get_text().strip():
                return True
            if isinstance(item, LTContainer) and chars(item):
                return True
        return False

    try:
        return any(chars(page) for page in extract_pages(str(path), maxpages=pages))
    except Exception:  # noqa: BLE001 - unreadable PDFs simply do not qualify
        return False


def fetch(book: dict, out: Path, text_only: bool) -> dict | None:
    target = out / f"{book['book_id']}.pdf"
    try:
        sha = (
            hashlib.sha256(target.read_bytes()).hexdigest()
            if target.exists()
            else download(book["url"], target)
        )
    except OSError as error:
        print(f"skip {book['book_id']}: {error}", file=sys.stderr)
        return None
    text = has_text_layer(target)
    if text_only and not text:
        target.unlink()
        return None
    return {**book, "sha256": sha, "file": target.name, "text_layer": text}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--out", type=Path, default=Path("corpus/shamela"))
    parser.add_argument("--per-category", type=int, default=2)
    parser.add_argument("--max-mb", type=float, default=25)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--text-only", action="store_true", help="delete PDFs without any text layer"
    )
    args = parser.parse_args()

    if not args.db.is_file():
        sys.exit(f"Shamela catalogue not found: {args.db} (install the desktop app or pass --db)")
    args.out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(args.seed)
    picked = []
    for _, books in sorted(candidates(args.db, int(args.max_mb * 2**20)).items()):
        picked += rng.sample(books, min(args.per_category, len(books)))

    with (
        ThreadPoolExecutor(8) as pool,
        (args.out / "manifest.jsonl").open("w", encoding="utf-8") as manifest,
    ):
        for book in pool.map(lambda b: fetch(b, args.out, args.text_only), picked):
            if book is None:
                continue
            manifest.write(json.dumps(book, ensure_ascii=False) + "\n")
            layer = "text" if book["text_layer"] else "scan"
            print(f"{book['book_id']:>6} {layer} {book['category']} | {book['name']}")


if __name__ == "__main__":
    main()
