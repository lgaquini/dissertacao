"""
Integração com Ollama para geração de respostas terapêuticas.
"""

from ollama import Client

from config import (
    CONTEXT_MODE,
    KNOWLEDGE_PLACEHOLDER,
    LLM_MODEL,
    LLM_NUM_CTX,
    LLM_TEMPERATURE,
    LLM_THINK,
    SYSTEM_PROMPT_BASE,
)
from context import build_context, knowledge_instruction

_client: Client | None = None


def get_client() -> Client:
    global _client
    if _client is None:
        _client = Client()  # conecta ao Ollama local (http://localhost:11434)
    return _client


def build_system_prompt(mode: str, context: str) -> str:
    """
    Monta o system prompt do braço `mode`. A instrução de fonte de conhecimento
    é a única parte que varia entre os braços; o bloco de contexto só é anexado
    quando há contexto recuperado.
    """
    prompt = SYSTEM_PROMPT_BASE.replace(
        KNOWLEDGE_PLACEHOLDER, knowledge_instruction(mode)
    )
    if context:
        prompt += (
            "\n\nCONTEXTO HISTÓRICO RECUPERADO (use para enriquecer a conversa):\n"
            + context
        )
    return prompt


def build_messages(
    history: list[dict],
    user_text: str,
    context: str,
    mode: str = CONTEXT_MODE,
) -> list[dict]:
    """
    Monta a lista de mensagens para o Ollama.
    `history` é uma lista de {"role": "user"|"assistant", "content": "..."}.
    """
    messages = [{"role": "system", "content": build_system_prompt(mode, context)}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_text})
    return messages


def chat(
    history: list[dict],
    user_text: str,
    mode: str = CONTEXT_MODE,
) -> tuple[str, list[dict]]:
    """
    Recebe o histórico da conversa e a fala atual do usuário,
    monta o contexto conforme o braço experimental ativo e retorna
    (resposta, chunks_recuperados). No modo closed_book os chunks vêm vazios.
    """
    context, chunks = build_context(user_text, mode)
    messages = build_messages(history, user_text, context, mode)

    client = get_client()
    response = client.chat(
        model=LLM_MODEL,
        messages=messages,
        think=LLM_THINK,
        options={
            "temperature": LLM_TEMPERATURE,
            "num_ctx": LLM_NUM_CTX,
        },
    )

    return response.message.content.strip(), chunks
