import html

import streamlit as st

from audio.tts import piper_available, speak
from config import CONTEXT_MODE, INTERFACE_MODE, INTERFACE_MODES
from context import retrieval_enabled
from llm.chat import chat

st.set_page_config(
    page_title="Memória — Terapia de Reminiscência",
    page_icon="🧠",
    layout="centered",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Merriweather:ital,wght@0,400;0,700;1,400&family=Playfair+Display:wght@700;900&display=swap');

    .main {
        background-color: #faf8f4;
    }

    /* Cabeçalho estilo jornal */
    .newspaper-header {
        text-align: center;
        border-bottom: 4px double #2c2c2c;
        padding-bottom: 0.6rem;
        margin-bottom: 0.3rem;
    }
    .newspaper-header h1 {
        font-family: 'Playfair Display', 'Georgia', serif;
        font-size: 2.8rem;
        font-weight: 900;
        color: #1a1a1a;
        letter-spacing: 0.08em;
        margin: 0;
        text-transform: uppercase;
    }
    .newspaper-subtitle {
        font-family: 'Merriweather', 'Georgia', serif;
        font-style: italic;
        font-size: 0.95rem;
        color: #666;
        margin-top: 0.2rem;
    }
    .newspaper-rule {
        border: none;
        border-top: 1px solid #2c2c2c;
        margin: 0.4rem 0 1.2rem 0;
    }

    /* Área da conversa */
    .conversation-area {
        background: #faf8f4;
        max-height: 58vh;
        overflow-y: auto;
        padding: 0.5rem 0;
        margin-bottom: 1rem;
    }

    /* Bloco de fala — estilo parágrafo de livro */
    .turn {
        font-family: 'Merriweather', 'Georgia', serif;
        font-size: 1.1rem;
        line-height: 1.75;
        color: #2c2c2c;
        margin-bottom: 1rem;
        padding: 0 0.5rem;
        text-align: justify;
    }
    .turn-speaker {
        font-weight: 700;
        font-variant: small-caps;
        font-size: 1.0rem;
        letter-spacing: 0.05em;
    }
    .turn-user .turn-speaker { color: #3a5a3a; }
    .turn-assistant .turn-speaker { color: #4a3a6a; }
    .turn-text {
        margin-left: 0.3rem;
    }

    /* Separador entre turnos */
    .turn-sep {
        text-align: center;
        color: #bbb;
        font-size: 0.9rem;
        margin: 0.3rem 0 0.8rem 0;
        letter-spacing: 0.5em;
    }

    /* Botão */
    div.stButton > button {
        width: 100%;
        height: 3.5rem;
        font-family: 'Merriweather', 'Georgia', serif;
        font-size: 1.15rem;
        border-radius: 4px;
        background-color: #faf8f4;
        color: #2c2c2c;
        border: 2px solid #2c2c2c;
        cursor: pointer;
        letter-spacing: 0.05em;
        transition: all 0.2s;
    }
    div.stButton > button:hover {
        background-color: #2c2c2c;
        color: #faf8f4;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

if "history" not in st.session_state:
    st.session_state.history: list[dict] = []

if "last_chunks" not in st.session_state:
    st.session_state.last_chunks: list[dict] = []

if "last_query" not in st.session_state:
    st.session_state.last_query: str = ""

if "interface_mode" not in st.session_state:
    st.session_state.interface_mode: str = INTERFACE_MODE


def _history_html() -> str:
    if not st.session_state.history:
        if st.session_state.interface_mode == "voz":
            placeholder = "Pressione o botão abaixo e conte-me uma história..."
        else:
            placeholder = "Escreva abaixo e conte-me uma história..."
        return (
            '<div class="conversation-area">'
            '<p style="font-family: Merriweather, Georgia, serif; '
            'font-style: italic; color: #999; text-align: center; '
            'padding: 3rem 1rem;">'
            f'{placeholder}'
            '</p></div>'
        )

    parts = ""
    for i, msg in enumerate(st.session_state.history):
        if msg["role"] == "user":
            speaker = "Você"
            cls = "turn-user"
        else:
            speaker = "Memória"
            cls = "turn-assistant"

        parts += (
            f'<div class="turn {cls}">'
            f'<span class="turn-speaker">{speaker}:</span> '
            f'<span class="turn-text">{html.escape(msg["content"])}</span>'
            f'</div>'
        )

        # Separador ornamental entre pares de turnos
        if msg["role"] == "assistant" and i < len(st.session_state.history) - 1:
            parts += '<div class="turn-sep">* * *</div>'

    return f'<div class="conversation-area">{parts}</div>'


def _respond(user_text: str) -> str:
    """Registra a fala do usuário, gera a resposta e a registra no histórico."""
    st.session_state.last_query = user_text
    st.session_state.history.append({"role": "user", "content": user_text})

    with st.spinner("Pensando..."):
        response, chunks = chat(
            history=st.session_state.history[:-1],
            user_text=user_text,
        )

    st.session_state.last_chunks = chunks
    st.session_state.history.append({"role": "assistant", "content": response})
    return response


# ── Cabeçalho ──────────────────────────────────────────────────────────────────
st.markdown(
    """
    <div class="newspaper-header">
        <h1>Memória</h1>
        <div class="newspaper-subtitle">Terapia de Reminiscência</div>
    </div>
    <hr class="newspaper-rule">
    """,
    unsafe_allow_html=True,
)

tab_chat, tab_debug = st.tabs(["Conversa", "Debug"])

# ── Aba principal ──────────────────────────────────────────────────────────────
with tab_chat:
    history_slot = st.empty()

    if st.session_state.interface_mode == "voz":
        if st.button("Pressione para falar"):
            # Import local: no modo texto o microfone (sounddevice/PortAudio) e o
            # faster-whisper nunca são carregados.
            from audio.stt import record_and_transcribe

            with st.spinner("Gravando... fale quando quiser."):
                user_text = record_and_transcribe()

            if not user_text:
                st.warning("Não consegui entender. Tente falar mais próximo do microfone.")
            else:
                response = _respond(user_text)
                history_slot.markdown(_history_html(), unsafe_allow_html=True)

                if piper_available():
                    with st.spinner("Falando..."):
                        speak(response)
    else:
        user_text = st.chat_input("Escreva sua mensagem...")
        if user_text and user_text.strip():
            _respond(user_text.strip())

    history_slot.markdown(_history_html(), unsafe_allow_html=True)

# ── Aba de debug ───────────────────────────────────────────────────────────────
with tab_debug:
    # O modo aparece só aqui, e não no cabeçalho: o participante não deve ver
    # rótulo de condição experimental, para não enviesar a interação.
    st.subheader("Braço experimental ativo")
    if retrieval_enabled():
        st.success(
            f"`{CONTEXT_MODE}` — recuperação ATIVA. "
            "O prompt recebe chunks do ChromaDB."
        )
    else:
        st.warning(
            f"`{CONTEXT_MODE}` — recuperação DESATIVADA. "
            "O modelo responde apenas com conhecimento paramétrico."
        )
    st.caption(
        "Para alternar: `MEMORIA_CONTEXT_MODE=closed_book streamlit run main.py` "
        "(ou edite `CONTEXT_MODE` em config.py). Confira este painel antes de "
        "iniciar uma sessão de coleta."
    )

    st.divider()
    st.subheader("Modo de interação")
    st.radio(
        "Entrada e saída",
        INTERFACE_MODES,
        key="interface_mode",
        format_func={
            "voz": "Voz — microfone e resposta falada",
            "texto": "Texto — digitar e ler na tela",
        }.get,
        horizontal=True,
    )
    st.caption(
        "Troca na hora, mantendo a conversa. Modo inicial: "
        "`MEMORIA_INTERFACE_MODE=texto streamlit run main.py` "
        "(ou edite `INTERFACE_MODE` em config.py)."
    )

    st.divider()
    st.subheader("Última consulta")

    if st.session_state.last_query:
        st.markdown(f"**Query:** `{st.session_state.last_query}`")
    else:
        st.info("Nenhuma consulta realizada ainda.")

    if retrieval_enabled():
        if st.session_state.last_chunks:
            chunks = st.session_state.last_chunks
            st.markdown(f"**{len(chunks)} chunk(s) recuperado(s):**")
            for i, chunk in enumerate(chunks, 1):
                with st.expander(
                    f"Chunk {i} — {chunk['source']} (chunk #{chunk['chunk']}) "
                    f"| distância: {chunk['distance']}"
                ):
                    st.text(chunk["document"])
        elif st.session_state.last_query:
            st.warning("Nenhum chunk recuperado para essa query.")
    elif st.session_state.last_query:
        st.info(
            "Modo closed-book: nenhum chunk foi recuperado nesta resposta — "
            "por desenho, não por falha."
        )

    st.divider()
    st.subheader("Inspecionar o índice")
    st.caption(
        "Consulta direta ao ChromaDB, independente do braço ativo. "
        "Não afeta a conversa."
    )

    manual_query = st.text_input("Testar busca manualmente:")
    if manual_query:
        from rag.retriever import retrieve_raw

        manual_chunks = retrieve_raw(manual_query)
        if manual_chunks:
            st.markdown(f"**{len(manual_chunks)} chunk(s):**")
            for i, chunk in enumerate(manual_chunks, 1):
                with st.expander(
                    f"Chunk {i} — {chunk['source']} (chunk #{chunk['chunk']}) "
                    f"| distância: {chunk['distance']}"
                ):
                    st.text(chunk["document"])
        else:
            st.warning("Nenhum chunk recuperado para essa query.")
