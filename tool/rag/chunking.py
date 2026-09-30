"""Structure-aware chunking for the knowledge sources.

Two chunkers, one per source shape:

- `chunk_dictionary` — dictionary-style markdown in data/livros (below).
- `chunk_sectioned_text` — the essay-style .txt files in data/historia
  (see its docstring).

Both dictionaries share a heading convention: each verbete (entry) starts
with a short headword followed by "." or ":" and a space, e.g.
"Abolição. O processo de Abolição...". Bibliography/source sub-sections
("Bibliografia.─ Garcia...", "Fontes.─ ...") don't match that shape — the
dash sits right after the period with no space — so they stay attached to
the entry they belong to instead of being split off as their own chunk.

Entries range from a few hundred to 20k+ characters. Splitting purely on
verbete boundaries would blow past the LLM's context budget for the long
ones, so entries longer than `max_chars` are further split on sentence
boundaries (never mid-sentence, per the project's chunking requirement).
Every resulting piece is prefixed with its headword so it stays
self-contained if retrieved on its own, without the entry's opening
sentence for context.
"""

import re
from dataclasses import dataclass

_ENTRY_HEADING = re.compile(r"^([A-ZÀ-Ü][^.:\n]{0,58}?)[.:]\s")
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+(?=[A-ZÀ-Ü0-9\"“(])")
_WHITESPACE = re.compile(r"\s+")


@dataclass
class DictionaryChunk:
    headword: str
    part: int
    parts_total: int
    text: str


def _normalize(text: str) -> str:
    return _WHITESPACE.sub(" ", text).strip()


def _split_entries(text: str) -> list[tuple[str, str]]:
    """Group paragraphs into (headword, full_entry_text) pairs."""
    paragraphs = re.split(r"\n\s*\n", text)
    entries: list[tuple[str, str]] = []
    headword: str | None = None
    body: list[str] = []

    for raw_paragraph in paragraphs:
        paragraph = _normalize(raw_paragraph)
        if not paragraph:
            continue
        match = _ENTRY_HEADING.match(paragraph)
        if match:
            if headword is not None:
                entries.append((headword, " ".join(body)))
            headword = _normalize(match.group(1))
            body = [paragraph]
        elif headword is not None:
            body.append(paragraph)

    if headword is not None:
        entries.append((headword, " ".join(body)))

    return entries


def _split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_BOUNDARY.split(text) if s.strip()]


def _group_sentences(sentences: list[str], max_chars: int) -> list[str]:
    """Greedily pack sentences into groups no longer than max_chars."""
    groups: list[str] = []
    current: list[str] = []
    current_len = 0

    for sentence in sentences:
        if current and current_len + len(sentence) + 1 > max_chars:
            groups.append(" ".join(current))
            current = [sentence]
            current_len = len(sentence)
        else:
            current.append(sentence)
            current_len += len(sentence) + 1

    if current:
        groups.append(" ".join(current))

    return groups


def chunk_dictionary(text: str, max_chars: int = 500) -> list[DictionaryChunk]:
    """Split a dictionary's markdown text into one chunk per verbete,
    sub-splitting entries longer than max_chars on sentence boundaries."""
    chunks: list[DictionaryChunk] = []

    for headword, body in _split_entries(text):
        if len(body) <= max_chars:
            chunks.append(DictionaryChunk(headword, 1, 1, body))
            continue

        pieces = _group_sentences(_split_sentences(body), max_chars)
        for i, piece in enumerate(pieces, start=1):
            piece_text = piece if piece.startswith(headword) else f"{headword}: {piece}"
            chunks.append(DictionaryChunk(headword, i, len(pieces), piece_text))

    return chunks


# ── Essay-style .txt (data/historia) ──────────────────────────────────────────
#
# Layout: the first paragraph is the document title, section headings are
# single-line paragraphs with no closing punctuation ("O Golpe de 1964"), and
# the rest are prose paragraphs. A lead-in such as "...transformações:" ends
# with ":" so it is kept as prose, together with the list that follows it.
_SECTION_HEADING = re.compile(r"^[^\n]{1,90}$")
_CLOSING_PUNCTUATION = re.compile(r"[.!?:;…]$")


@dataclass
class SectionChunk:
    title: str
    section: str | None
    text: str


def _is_section_heading(paragraph: str) -> bool:
    return bool(_SECTION_HEADING.match(paragraph)) and not _CLOSING_PUNCTUATION.search(
        paragraph
    )


def chunk_sectioned_text(text: str, max_chars: int = 500) -> list[SectionChunk]:
    """Split a titled, sectioned text into chunks that never cross a section
    boundary or cut a sentence.

    Consecutive paragraphs of the same section are packed together up to
    max_chars; a paragraph longer than that is split on sentence boundaries.
    Every chunk is prefixed with "Title — Section:" so a passage that never
    names its topic (e.g. one about the AI-5, under the dictatorship file)
    still carries it when embedded and when shown to the LLM on its own.
    """
    paragraphs = [_normalize(p) for p in re.split(r"\n\s*\n", text)]
    paragraphs = [p for p in paragraphs if p]
    if not paragraphs:
        return []

    title, paragraphs = paragraphs[0], paragraphs[1:]
    chunks: list[SectionChunk] = []
    section: str | None = None
    pending: list[str] = []

    def flush() -> None:
        if not pending:
            return
        for group in _group_sentences(pending, max_chars):
            prefix = f"{title} — {section}" if section else title
            chunks.append(SectionChunk(title, section, f"{prefix}: {group}"))
        pending.clear()

    for paragraph in paragraphs:
        if _is_section_heading(paragraph):
            flush()
            section = paragraph
        elif len(paragraph) > max_chars:
            pending.extend(_split_sentences(paragraph))
        else:
            pending.append(paragraph)

    flush()
    return chunks
