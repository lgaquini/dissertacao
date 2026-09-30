"""Semantic chunking for the dictionary-style markdown sources (data/livros).

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
