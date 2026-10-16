"""Character n-gram model of Arabic letter sequences (interpolated Witten-Bell)."""

from __future__ import annotations

import gzip
import json
import math
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from pathlib import Path

from .normalize import ALPHABET, BOUNDARY

FORMAT_VERSION = 1


class CharLM:
    """Interpolated Witten-Bell character model over `ALPHABET`.

    `counts[context][char]` holds raw counts for every context length from 0 to order - 1.
    """

    def __init__(self, order: int, counts: dict[str, dict[str, int]], metadata: dict | None = None):
        if order < 1:
            raise ValueError("order must be >= 1")
        self.order = order
        self.metadata = metadata or {}
        self._counts = counts
        # (total, distinct types) per context, needed by every probability lookup.
        self._stats = {ctx: (sum(c.values()), len(c)) for ctx, c in counts.items()}
        self._base = 1.0 / len(ALPHABET)

    @classmethod
    def train(cls, texts: Iterable[str], order: int = 4, metadata: dict | None = None) -> CharLM:
        """Train on texts already reduced by `normalize.letters_only`."""
        counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for text in texts:
            padded = _pad(text, order)
            for i in range(order - 1, len(padded)):
                for k in range(order):
                    counts[padded[i - k : i]][padded[i]] += 1
        frozen = {ctx: dict(chars) for ctx, chars in counts.items()}
        return cls(order, frozen, metadata)

    def prob(self, char: str, history: str) -> float:
        p = self._base
        history = history[-(self.order - 1) :] if self.order > 1 else ""
        for k in range(len(history) + 1):
            ctx = history[len(history) - k :]
            chars = self._counts.get(ctx)
            if chars is None:
                break  # Longer contexts cannot exist if this one was never seen.
            total, types = self._stats[ctx]
            p = (chars.get(char, 0) + types * p) / (total + types)
        return p

    def surprisals(self, text: str) -> list[float]:
        """Negative log2 probability of each letter of `text` and of its closing boundary."""
        padded = _pad(text, self.order)
        start = self.order - 1
        return [
            -math.log2(self.prob(padded[i], padded[i - start : i]))
            for i in range(start, len(padded))
        ]

    def bits_per_char(self, text: str) -> tuple[float, int]:
        """Average surprisal of the letters in `text`, and how many were scored."""
        values = self.surprisals(text)
        return (sum(values) / len(values) if values else 0.0), len(values)

    def to_json(self) -> dict:
        return {
            "format": FORMAT_VERSION,
            "order": self.order,
            "alphabet": ALPHABET,
            "metadata": self.metadata,
            "counts": {ctx: dict(sorted(c.items())) for ctx, c in sorted(self._counts.items())},
        }

    def save(self, path: Path) -> None:
        payload = json.dumps(self.to_json(), ensure_ascii=False, separators=(",", ":"))
        # Empty embedded filename and mtime=0 keep the packaged artifact byte-reproducible.
        with (
            path.open("wb") as raw,
            gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0) as fh,
        ):
            fh.write(payload.encode("utf-8"))

    @classmethod
    def load(cls, path: Path) -> CharLM:
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            data = json.load(fh)
        if data.get("format") != FORMAT_VERSION or data.get("alphabet") != ALPHABET:
            raise ValueError(f"Incompatible harfix model file: {path}")
        return cls(data["order"], data["counts"], data.get("metadata"))


def _pad(text: str, order: int) -> str:
    # Leading context of boundaries, and one trailing boundary so word endings are scored.
    return BOUNDARY * (order - 1) + text + BOUNDARY


@dataclass(frozen=True)
class ModelPair:
    """`spaced` sees word boundaries; `unspaced` was trained with every space removed.

    The unspaced model tells extractor spacing errors apart from wrong letters.
    """

    spaced: CharLM
    unspaced: CharLM


def _packaged(name: str) -> CharLM:
    with resources.as_file(resources.files("harfix") / "data" / name) as path:
        return CharLM.load(path)


@lru_cache(maxsize=1)
def default_models() -> ModelPair:
    return ModelPair(
        _packaged("arabic_char_lm.json.gz"), _packaged("arabic_char_lm_unspaced.json.gz")
    )
