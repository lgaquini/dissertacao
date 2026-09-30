#!/usr/bin/env python3
"""Remove leftover PDF page-number lines from dic1.md.

Page breaks in the source PDF were extracted as a standalone number line
followed by a form-feed character (\\x0c), e.g.:

    ...Museu de Arte Moder-

    19

    na, tendo como professor...

The text after the break is a mid-sentence line continuation (never a new
paragraph), so the number + form-feed block is dropped and replaced with a
single newline, matching the line-wrap style used elsewhere in the file.
"""

import re
from pathlib import Path

FILE = Path(__file__).resolve().parent.parent / "data" / "livros" / "dic1.md"

PAGE_BREAK_PATTERN = re.compile(r"\n\n\d+\n\n\x0c\n")

# Front-matter page number with no form-feed marker (precedes a heading).
FRONT_MATTER_CASE = ("Uma boa leitura a todas e todos.\n\n3\n\nAPRESENTAÇÃO",
                     "Uma boa leitura a todas e todos.\n\nAPRESENTAÇÃO")


def main() -> None:
    text = FILE.read_text(encoding="utf-8")

    old, new = FRONT_MATTER_CASE
    front_matter_fixed = 0
    if old in text:
        text = text.replace(old, new)
        front_matter_fixed = 1

    text, page_breaks_fixed = PAGE_BREAK_PATTERN.subn("\n", text)

    FILE.write_text(text, encoding="utf-8")
    print(f"Removed {page_breaks_fixed} page-break number blocks")
    print(f"Removed {front_matter_fixed} front-matter page number")


if __name__ == "__main__":
    main()
