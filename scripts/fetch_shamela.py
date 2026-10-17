"""Download a seeded sample of book PDFs listed in a local al-Maktaba al-Shamela install.

The Shamela desktop app keeps its catalogue in `database/master.db`; about 1,200 books link
a printed-edition PDF hosted on archive.org. This picks a fixed number per subject category
(so grammar, poetry, hadith and tafsir are all represented), downloads them, and writes a
`manifest.jsonl` with the URL and SHA-256 of every file. The PDFs are third-party works:
keep them local, never commit or redistribute them.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sqlite3
import sys
import urllib.request
from pathlib import Path

DEFAULT_DB = Path.home() / "Library/Application Support/Shamela/database/master.db"


def candidates(db: Path, max_bytes: int) -> dict[str, list[dict]]:
    """Books whose single PDF is on archive.org, grouped by category name."""
    query = """
        select b.book_id, b.book_name, c.category_name, b.pdf_links
        from book b join category c on c.category_id = b.book_category
        where b.pdf_links like '%archive.org%'
        order by b.book_id
    """
    by_category: dict[str, list[dict]] = {}
    with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as conn:
        for book_id, name, category, links in conn.execute(query):
            info = json.loads(links)
            files = info.get("files", [])
            if len(files) != 1 or not files[0].startswith("https://archive.org/"):
                continue
            if not 0 < info.get("size", 0) <= max_bytes:
                continue
            by_category.setdefault(category, []).append(
                {"book_id": book_id, "name": name, "category": category, "url": files[0]}
            )
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--out", type=Path, default=Path("corpus/shamela"))
    parser.add_argument("--per-category", type=int, default=2)
    parser.add_argument("--max-mb", type=float, default=25)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    if not args.db.is_file():
        sys.exit(f"Shamela catalogue not found: {args.db} (install the desktop app or pass --db)")
    args.out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(args.seed)
    picked = []
    for _, books in sorted(candidates(args.db, int(args.max_mb * 2**20)).items()):
        picked += rng.sample(books, min(args.per_category, len(books)))

    with (args.out / "manifest.jsonl").open("w", encoding="utf-8") as manifest:
        for book in picked:
            target = args.out / f"{book['book_id']}.pdf"
            try:
                book["sha256"] = (
                    hashlib.sha256(target.read_bytes()).hexdigest()
                    if target.exists()
                    else download(book["url"], target)
                )
            except OSError as error:
                print(f"skip {book['book_id']}: {error}", file=sys.stderr)
                continue
            book["file"] = target.name
            manifest.write(json.dumps(book, ensure_ascii=False) + "\n")
            print(f"{book['book_id']:>6} {book['category']} | {book['name']}")


if __name__ == "__main__":
    main()
