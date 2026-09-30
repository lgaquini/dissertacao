"""
Script de ingestão: lê arquivos de texto e PDFs da pasta data/historia/,
divide em chunks e indexa no ChromaDB.

Uso (a partir de tool/):
    uv run ingest            # ou: uv run python -m rag.ingest
"""

import hashlib
import sys
from pathlib import Path

from pypdf import PdfReader

from config import CHUNK_OVERLAP, CHUNK_SIZE, DATA_DIR, DICTIONARY_FILES, LIVROS_DIR
from rag.chunking import chunk_dictionary
from rag.embeddings import embed
from rag.vectorstore import get_collection


def _read_file(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    return path.read_text(encoding="utf-8", errors="ignore")


def _chunk(
    text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP
) -> list[str]:
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end].strip())
        start += size - overlap
    return [c for c in chunks if len(c) > 50]  # descarta chunks muito pequenos


def _doc_id(source: str, index: int) -> str:
    digest = hashlib.md5(source.encode()).hexdigest()[:8]
    return f"{digest}_{index}"


def ingest_file(path: Path, collection) -> int:
    text = _read_file(path)

    if path.name in DICTIONARY_FILES:
        entries = chunk_dictionary(text)
        if not entries:
            return 0
        chunks = [e.text for e in entries]
        metadatas = [
            {
                "source": path.name,
                "chunk": i,
                "headword": e.headword,
                "part": e.part,
                "parts_total": e.parts_total,
            }
            for i, e in enumerate(entries)
        ]
    else:
        chunks = _chunk(text)
        if not chunks:
            return 0
        metadatas = [{"source": path.name, "chunk": i} for i in range(len(chunks))]

    ids = [_doc_id(path.name, i) for i in range(len(chunks))]
    embeddings = embed(chunks)

    # upsert evita duplicatas ao re-ingerir o mesmo arquivo
    collection.upsert(
        ids=ids,
        embeddings=embeddings,
        documents=chunks,
        metadatas=metadatas,
    )
    return len(chunks)


def main():
    if not DATA_DIR.exists():
        print(f"[ingest] Pasta não encontrada: {DATA_DIR}")
        print("[ingest] Crie a pasta e adicione arquivos .txt ou .pdf de história.")
        sys.exit(1)

    files = list(DATA_DIR.glob("**/*.txt")) + list(DATA_DIR.glob("**/*.pdf"))
    files += [
        LIVROS_DIR / name for name in DICTIONARY_FILES if (LIVROS_DIR / name).exists()
    ]
    if not files:
        print(f"[ingest] Nenhum arquivo .txt ou .pdf encontrado em {DATA_DIR}")
        sys.exit(1)

    collection = get_collection()
    total = 0
    for f in files:
        n = ingest_file(f, collection)
        print(f"[ingest] {f.name}: {n} chunks indexados")
        total += n

    print(f"\n[ingest] Concluído. Total de chunks: {total}")


if __name__ == "__main__":
    main()
