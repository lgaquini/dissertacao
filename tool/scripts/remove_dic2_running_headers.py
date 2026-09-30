#!/usr/bin/env python3
"""Remove running-header lines from dic2.md.

Each page top/bottom repeats the current verbete name and its letter as a
pipe-delimited pair, in one of two orders depending on left/right page:

    | A | Administração
    Administração | A |

These are page furniture from the source PDF, not article content.
"""

import re
from pathlib import Path

FILE = Path(__file__).resolve().parent.parent / "data" / "livros" / "dic2.md"

LETTER_FIRST = r"\|\s*[A-ZÀ-Ü]\s*\|\s*.+"   # | A | Headword
LETTER_LAST = r".+\s*\|\s*[A-ZÀ-Ü]\s*\|"    # Headword | A |
# A page-break form-feed (\x0c) sometimes sits glued to the front of the
# header line, left over from the page boundary; drop it along with the
# header since it belongs to the same artifact.
RUNNING_HEADER = re.compile(
    rf"\n\n\x0c?[ \t]*(?:{LETTER_FIRST}|{LETTER_LAST})[ \t]*\n\n"
)


def main() -> None:
    text = FILE.read_text(encoding="utf-8")
    text, removed = RUNNING_HEADER.subn("\n\n", text)
    FILE.write_text(text, encoding="utf-8")
    print(f"Removed {removed} running-header lines")


if __name__ == "__main__":
    main()
