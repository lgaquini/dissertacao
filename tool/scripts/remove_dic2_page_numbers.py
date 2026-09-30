#!/usr/bin/env python3
"""Remove leftover PDF page-number markers from dic2.md, e.g. '| 18 |'."""

import re
from pathlib import Path

FILE = Path(__file__).resolve().parent.parent / "data" / "livros" / "dic2.md"

PAGE_NUMBER_PATTERN = re.compile(r"\n\n\|\s*\d+\s*\|\n\n")


def main() -> None:
    text = FILE.read_text(encoding="utf-8")
    text, removed = PAGE_NUMBER_PATTERN.subn("\n\n", text)
    FILE.write_text(text, encoding="utf-8")
    print(f"Removed {removed} page-number markers")


if __name__ == "__main__":
    main()
