#!/usr/bin/env python3
"""Fix drop-cap extraction artifacts in dic1.md.

The source PDF sets each verbete's first letter as a large decorative
drop cap. Text extraction pulled that letter onto its own line, split
from the rest of the word by blank lines — in most entries right before
the continuation ("A\n\nrtesãos." -> "Artesãos."), but in four entries
the letter instead landed near the page-break footer that follows the
paragraph, leaving the entry itself starting mid-word ("onselho
Municipal..." -> "Conselho Municipal...").
"""

import re
from pathlib import Path

FILE = Path(__file__).resolve().parent.parent / "data" / "livros" / "dic1.md"

# Reversed cases: (word missing its first letter, orphan letter block to drop).
# Idempotent: skipped if new_word is already present (i.e. already fixed).
REVERSED_CASES = [
    (
        "onselho  Municipal  (1891-1935)",
        "Conselho  Municipal  (1891-1935)",
        "\n\nC\n\n93",
        "\n\n93",
    ),
    (
        "aculdade  de  Direito.  A  ideia",
        "Faculdade  de  Direito.  A  ideia",
        "\n\nF\n\n135",
        "\n\n135",
    ),
    (
        "mprensa.A  imprensa  surgiu",
        "Imprensa.A  imprensa  surgiu",
        "\n\nI\n\n160",
        "\n\n160",
    ),
    (
        "uas. A ocupação do espaço",
        "Ruas. A ocupação do espaço",
        "\n\nR\n\n(Érica Lopes de Lima)",
        "\n\n(Érica Lopes de Lima)",
    ),
]

# A drop-cap letter alone on its own line, followed by a blank line, followed
# by the rest of its word. The line *before* the letter varies (blank line,
# or a form-feed page-break marker), so it is intentionally not matched.
FORWARD_PATTERN = re.compile(r"(?m)^([A-ZÀ-ÖØ-Þ])\n\n(?=[a-zà-ÿ])")

# Same drop-cap bug, but with no blank line separating the letter from the
# rest of its word.
FORWARD_PATTERN_NO_GAP = re.compile(r"(?m)^([A-ZÀ-ÖØ-Þ])\n(?=[a-zà-ÿ])")


def main() -> None:
    text = FILE.read_text(encoding="utf-8")

    reversed_fixed = 0
    for old_word, new_word, old_block, new_block in REVERSED_CASES:
        if new_word in text:
            continue  # already fixed
        assert text.count(old_word) == 1, f"expected exactly one match for {old_word!r}"
        assert text.count(old_block) == 1, f"expected exactly one match for {old_block!r}"
        text = text.replace(old_word, new_word).replace(old_block, new_block)
        reversed_fixed += 1

    text, forward_fixed = FORWARD_PATTERN.subn(r"\1", text)
    text, no_gap_fixed = FORWARD_PATTERN_NO_GAP.subn(r"\1", text)

    FILE.write_text(text, encoding="utf-8")
    print(f"Fixed {forward_fixed} forward drop-cap cases")
    print(f"Fixed {no_gap_fixed} forward drop-cap cases (no blank line)")
    print(f"Fixed {reversed_fixed} reversed drop-cap cases")


if __name__ == "__main__":
    main()
