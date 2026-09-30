from config import RAG_TOP_K
from rag.embeddings import embed
from rag.vectorstore import get_collection


def retrieve_raw(query: str, top_k: int = RAG_TOP_K) -> list[dict]:
    """
    Retorna lista de chunks com documento, metadados e distância.
    Útil para debug e inspeção.
    """
    collection = get_collection()

    if collection.count() == 0:
        return []

    query_embedding = embed([query])[0]

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(top_k, collection.count()),
        include=["documents", "metadatas", "distances"],
    )

    chunks = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        chunks.append(
            {
                "document": doc,
                "source": meta.get("source", "desconhecido"),
                "chunk": meta.get("chunk", 0),
                "headword": meta.get("headword"),
                "distance": round(dist, 4),
            }
        )
    return chunks


def retrieve(query: str, top_k: int = RAG_TOP_K) -> str:
    """
    Busca os chunks mais relevantes para a query e retorna
    um bloco de contexto pronto para inserir no prompt do LLM.
    """
    chunks = retrieve_raw(query, top_k)

    if not chunks:
        return ""

    def _label(c: dict) -> str:
        if c["headword"]:
            return f"{c['source']} — {c['headword']}"
        return c["source"]

    parts = [f"[Fonte: {_label(c)}]\n{c['document']}" for c in chunks]
    return "\n\n---\n\n".join(parts)
