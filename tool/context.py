"""
Provedor de contexto — define qual braço experimental a aplicação está rodando.

Modos (config.CONTEXT_MODE):
    rag         → recupera chunks do ChromaDB e injeta no prompt
    closed_book → sem recuperação; o LLM usa apenas conhecimento paramétrico

Para adicionar um modo novo (ex. static_era): escrever uma função com a mesma
assinatura, registrar em _PROVIDERS e acrescentar a instrução correspondente em
config.KNOWLEDGE_INSTRUCTION e config.CONTEXT_MODES.
"""

from config import CONTEXT_MODE, KNOWLEDGE_INSTRUCTION


def _context_rag(user_text: str) -> tuple[str, list[dict]]:
    # Import local e não no topo do módulo: no modo closed_book o
    # sentence-transformers (e o torch por trás dele) nunca é importado, o que
    # muda tempo de boot e RAM no Pi 5. Manter esse import aqui é o que torna a
    # comparação de latência entre os braços honesta.
    from rag.retriever import retrieve_raw

    chunks = retrieve_raw(user_text)
    if not chunks:
        return "", []

    block = "\n\n---\n\n".join(
        f"[Fonte: {c['source']}]\n{c['document']}" for c in chunks
    )
    return block, chunks


def _context_closed_book(user_text: str) -> tuple[str, list[dict]]:
    return "", []


_PROVIDERS = {
    "rag": _context_rag,
    "closed_book": _context_closed_book,
}


def build_context(user_text: str, mode: str = CONTEXT_MODE) -> tuple[str, list[dict]]:
    """
    Retorna (bloco_de_contexto, chunks_recuperados).
    Nos modos sem recuperação ambos vêm vazios.
    """
    return _PROVIDERS[mode](user_text)


def knowledge_instruction(mode: str = CONTEXT_MODE) -> str:
    """Linha do system prompt que declara de onde vêm os fatos históricos."""
    return KNOWLEDGE_INSTRUCTION[mode]


def retrieval_enabled(mode: str = CONTEXT_MODE) -> bool:
    return mode == "rag"
