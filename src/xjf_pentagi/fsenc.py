"""Decode text files that may be UTF-8, UTF-16 (incl. BOM-less LE), or legacy Windows encodings."""
from __future__ import annotations

from pathlib import Path


def read_text_flexible(path: Path) -> str:
    data = path.read_bytes()
    for enc in (
        "utf-8-sig",
        "utf-8",
        "utf-16",
        "utf-16-le",
        "utf-16-be",
        "gbk",
        "cp936",
    ):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")
