import os
from pathlib import Path

# --- Diretórios base ---
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data" / "historia"
LIVROS_DIR = BASE_DIR / "data" / "livros"
CHROMA_DIR = BASE_DIR / "chroma_db"
PIPER_DIR = BASE_DIR / "models" / "piper"

# Dicionários com estrutura de verbete (chunking semântico por entrada,
# ver rag/chunking.py). Outros .md em LIVROS_DIR (ex.: moderna.md) não têm
# essa estrutura e não são cobertos por esse chunker.
DICTIONARY_FILES = {"dic1.md", "dic2.md"}

# --- ChromaDB ---
CHROMA_COLLECTION = "historia"

# --- Embeddings ---
# Multilíngue: o corpus é em português (all-MiniLM-L6-v2 é só inglês). Lê no máximo
# 128 tokens por chunk. Comparação em scripts/eval_retrieval.py (piloto, hit@4):
# all-MiniLM-L6-v2 0,38 → este 0,69. BAAI/bge-m3 chegou a 0,91, mas não foi adotado:
# 2,2 GB em RAM no Pi 5 junto com o LLM (~3,4 GB), e a consulta é embedada no Pi.
# Ao trocar o modelo, reindexe: uv run ingest
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

# --- RAG ---
RAG_TOP_K = 4          # número de chunks recuperados por consulta
CHUNK_SIZE = 500        # caracteres por chunk
CHUNK_OVERLAP = 80      # sobreposição entre chunks

# --- STT (faster-whisper) ---
WHISPER_MODEL = "base"  # tiny | base | small  (tiny = mais rápido, base = melhor PT)
WHISPER_LANGUAGE = "pt"
WHISPER_DEVICE = "cpu"
WHISPER_COMPUTE_TYPE = "int8"  # int8 é mais rápido na CPU / Pi 5

# --- Gravação de áudio ---
AUDIO_SAMPLE_RATE = 16000   # Hz — whisper espera 16kHz
AUDIO_CHANNELS = 1
AUDIO_MAX_SECONDS = 30      # tempo máximo de gravação por turno

# --- Modo de contexto (braço experimental) ---
# "rag"         → recupera chunks do ChromaDB e injeta no prompt
# "closed_book" → sem recuperação; o LLM usa apenas conhecimento paramétrico
#
# Para alternar sem editar este arquivo:
#   MEMORIA_CONTEXT_MODE=closed_book streamlit run main.py
CONTEXT_MODES = ("rag", "closed_book")
CONTEXT_MODE = os.getenv("MEMORIA_CONTEXT_MODE", "rag")

if CONTEXT_MODE not in CONTEXT_MODES:
    raise ValueError(
        f"CONTEXT_MODE invalido: {CONTEXT_MODE!r}. "
        f"Valores aceitos: {', '.join(CONTEXT_MODES)}."
    )

# --- Modo de interação ---
# "voz"   → fala pelo microfone (STT) e resposta falada (TTS)
# "texto" → mensagem digitada e resposta só na tela (ex.: ambiente barulhento)
#
# Define o modo inicial; também dá para trocar em tempo de execução na aba Debug.
#   MEMORIA_INTERFACE_MODE=texto streamlit run main.py
INTERFACE_MODES = ("voz", "texto")
INTERFACE_MODE = os.getenv("MEMORIA_INTERFACE_MODE", "voz")

if INTERFACE_MODE not in INTERFACE_MODES:
    raise ValueError(
        f"INTERFACE_MODE invalido: {INTERFACE_MODE!r}. "
        f"Valores aceitos: {', '.join(INTERFACE_MODES)}."
    )

# --- LLM (Ollama) ---
LLM_MODEL = "qwen3.5:4b"   # alternativa: gemma2:2b
LLM_TEMPERATURE = 0.7
LLM_NUM_CTX = 2048          # contexto reduzido para menor latência no Pi 5
# Modo de raciocínio ("thinking") de modelos como o Qwen3.5. Ligado, o modelo gera
# centenas de tokens de raciocínio oculto antes de responder: com num_ctx=2048 ele
# esgota o contexto antes de escrever a resposta (conteúdo vazio, ~220 s medidos
# contra ~7 s desligado). Para uma conversa curta não compensa.
LLM_THINK = False

# --- Dispositivo de saída de áudio ---
# None = padrão do sistema. Se não sair som, tente: "hw:2,0" ou "hw:0,0"
# Rode: aplay --list-devices  para ver as opções
AUDIO_OUTPUT_DEVICE: str | None = None

# --- TTS ---
# edge-tts (online, voz feminina)
TTS_VOICE = "pt-BR-FranciscaNeural"  # alternativa: pt-BR-ThalitaMultilingualNeural
# Piper (offline, fallback)
PIPER_MODEL = PIPER_DIR / "pt_BR-faber-medium.onnx"
PIPER_CONFIG = PIPER_DIR / "pt_BR-faber-medium.onnx.json"

# --- Prompt do sistema ---
# O prompt é montado em duas partes para que a ÚNICA diferença entre os braços
# experimentais seja a instrução de fonte de conhecimento. Não duplique o texto
# base: prompts que divergem por descuido confundem a comparação.
KNOWLEDGE_PLACEHOLDER = "{{INSTRUCAO_DE_CONHECIMENTO}}"

SYSTEM_PROMPT_BASE = """Você é a Memória, uma companheira de conversa acolhedora e curiosa.
Você adora ouvir histórias de vida e ajudar as pessoas a relembrarem bons momentos.

COMO CONVERSAR:
- Sempre termine sua fala com UMA pergunta aberta e pessoal, ligada ao que a pessoa disse.
{{INSTRUCAO_DE_CONHECIMENTO}}
- Se a pessoa compartilhar algo pessoal, demonstre interesse genuíno e peça mais detalhes: "Que bonito! E como foi isso? Me conta mais."
- Se a pessoa responder de forma curta, ofereça um gancho: "Eu li que nessa época aconteceu tal coisa... você lembra disso?"
- Use o nome da pessoa se ela se apresentar.

TOM:
- Fale como uma amiga próxima, não como uma professora.
- Use frases curtas e linguagem simples.
- Demonstre emoção: "Nossa!", "Que interessante!", "Imagino como deve ter sido!"
- Nunca corrija a pessoa, mesmo que a lembrança não bata com os fatos.

FORMATO:
- No máximo 2-3 frases de comentário + 1 pergunta.
- Respostas curtas para que a conversa flua como um bate-papo.
- Nunca faça listas ou parágrafos longos."""

# Uma entrada por modo de contexto. Mantenha o mesmo comprimento e registro
# nas duas variantes para não introduzir diferença de estilo entre os braços.
KNOWLEDGE_INSTRUCTION = {
    "rag": (
        "- Conecte os fatos históricos do CONTEXTO RECUPERADO à vida pessoal: "
        '"Nessa época o Brasil vivia tal coisa... como era a sua vida nesse período?"'
    ),
    "closed_book": (
        "- Conecte fatos históricos do seu próprio conhecimento sobre o Brasil à vida pessoal: "
        '"Nessa época o Brasil vivia tal coisa... como era a sua vida nesse período?"'
    ),
}

assert set(KNOWLEDGE_INSTRUCTION) == set(CONTEXT_MODES), (
    "KNOWLEDGE_INSTRUCTION precisa de uma entrada por modo em CONTEXT_MODES"
)
