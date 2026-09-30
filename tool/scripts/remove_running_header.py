#!/usr/bin/env python3
"""Remove standalone 'Dicionário de História de Pelotas [X]' header lines from dic1.md."""

import re
from pathlib import Path

PATTERN = re.compile(r"^Dicionário de História de Pelotas \[.+\]$")
FILE = Path(__file__).resolve().parent.parent / "data" / "livros" / "dic1.md"


def main() -> None:
    lines = FILE.read_text(encoding="utf-8").splitlines(keepends=True)
    kept = [line for line in lines if not PATTERN.match(line.strip())]
    removed = len(lines) - len(kept)
    FILE.write_text("".join(kept), encoding="utf-8")
    print(f"Removed {removed} occurrence(s) from {FILE}")


if __name__ == "__main__":
    main()
