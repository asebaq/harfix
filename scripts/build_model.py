"""Build the packaged Arabic character model from pinned Apache-2.0 datasets.

Usage:
    uv run --group model python scripts/build_model.py

Writes:
    src/harfix/data/arabic_char_lm.json.gz            spaced model, "train" split only
    src/harfix/data/arabic_char_lm_unspaced.json.gz   same letters with spaces removed
    build/pages.jsonl                         every page with its split, for calibrate.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import duckdb

from harfix.model import CharLM
from harfix.normalize import letters_only

ROOT = Path(__file__).resolve().parent.parent

# Pinned revisions: the model must be reproducible from public sources.
SOURCES = [
    {
        "dataset": "Misraj/Misraj-DocOCR",
        "revision": "7177bf70f77ce259890d6af0bef53f18faf26ec9",
        "files": ["data/train-00000-of-00002.parquet", "data/train-00001-of-00002.parquet"],
        "license": "Apache-2.0",
    },
    {
        "dataset": "Misraj/KITAB_pdf_to_markdown_reviewed",
        "revision": "8890d721c660cd027839bc8bc48634552fe7aec6",
        "files": ["data/train-00000-of-00001.parquet"],
        "license": "Apache-2.0",
    },
]


def split_of(key: str) -> str:
    """Deterministic 70/15/15 split by content hash."""
    bucket = int(hashlib.sha256(key.encode("utf-8")).hexdigest(), 16) % 100
    if bucket < 70:
        return "train"
    return "calib" if bucket < 85 else "test"


def fetch_pages() -> list[dict]:
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")
    pages = []
    for source in SOURCES:
        for name in source["files"]:
            url = (
                f"https://huggingface.co/datasets/{source['dataset']}/resolve/"
                f"{source['revision']}/{name}"
            )
            # Only the markdown column is read; parquet range requests skip the images.
            for (markdown,) in con.execute(
                f"SELECT markdown FROM read_parquet('{url}')"
            ).fetchall():
                if not markdown:
                    continue
                key = hashlib.sha256(markdown.encode("utf-8")).hexdigest()
                pages.append(
                    {
                        "source": source["dataset"],
                        "id": key[:16],
                        "split": split_of(key),
                        "text": markdown,
                    }
                )
    return pages


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--order", type=int, default=4)
    args = parser.parse_args()

    pages = fetch_pages()
    build = ROOT / "build"
    build.mkdir(exist_ok=True)
    with (build / "pages.jsonl").open("w", encoding="utf-8") as fh:
        for page in pages:
            fh.write(json.dumps(page, ensure_ascii=False) + "\n")

    train = [letters_only(p["text"]) for p in pages if p["split"] == "train"]
    train = [t for t in train if t]
    metadata = {
        "sources": SOURCES,
        "split": "sha256(markdown) % 100 < 70",
        "train_pages": len(train),
        "train_letters": sum(len(t.replace(" ", "")) for t in train),
        "smoothing": "interpolated Witten-Bell",
    }
    data = ROOT / "src" / "harfix" / "data"
    variants = {
        "arabic_char_lm.json.gz": (train, "spaced"),
        "arabic_char_lm_unspaced.json.gz": ([t.replace(" ", "") for t in train], "unspaced"),
    }
    counts = {s: sum(1 for p in pages if p["split"] == s) for s in ("train", "calib", "test")}
    print(f"pages by split: {counts}")
    print(f"train letters: {metadata['train_letters']:,}")
    for filename, (texts, variant) in variants.items():
        model = CharLM.train(texts, order=args.order, metadata={**metadata, "variant": variant})
        model.save(data / filename)
        size = (data / filename).stat().st_size / 1024
        print(f"wrote src/harfix/data/{filename} ({size:.0f} KiB)")


if __name__ == "__main__":
    main()
