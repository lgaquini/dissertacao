# Memória — ferramenta

Aplicação Streamlit: fala do usuário (faster-whisper) → contexto histórico (ChromaDB, braço `rag`)
ou nenhum contexto (braço `closed_book`) → LLM local via Ollama → resposta falada (edge-tts, com Piper
como fallback offline).

Todos os comandos abaixo são executados **a partir desta pasta** (`tool/`).

## Estrutura

```
main.py          interface Streamlit
memoria/cli.py   launcher do comando `uv run memoria`
config.py        parâmetros (modelos, caminhos, prompt, braço experimental)
context.py       provedor de contexto por braço experimental
audio/           gravação + STT (stt.py) e TTS (tts.py)
llm/             cliente Ollama e montagem do prompt
rag/             chunking, embeddings, ChromaDB, ingestão e recuperação
scripts/         check_modes.py (verificação dos braços) e limpeza do corpus em data/livros
data/historia/   textos de história do Brasil (.txt)
data/livros/     dicionários/livros convertidos para .md (PDFs originais fora do git)
chroma_db/       índice vetorial gerado (fora do git)
models/piper/    voz do Piper (fora do git)
```

## Requisitos de sistema

- [uv](https://docs.astral.sh/uv/)
- [Ollama](https://ollama.com/) com o modelo de `config.LLM_MODEL`: `ollama pull qwen3.5:4b`
- PortAudio (para `sounddevice`; no Raspberry Pi OS: `sudo apt install libportaudio2`)
- `paplay` (PulseAudio/PipeWire) para tocar o áudio
- Voz do Piper em `models/piper/`: `pt_BR-faber-medium.onnx` e `pt_BR-faber-medium.onnx.json`
  (de [rhasspy/piper-voices](https://huggingface.co/rhasspy/piper-voices/tree/main/pt/pt_BR/faber/medium))

## Uso

```bash
uv sync                  # no Raspberry Pi: uv sync --no-dev (pula o markitdown)
uv run ingest                            # (re)constrói chroma_db/

uv run memoria                           # voz + braço rag (padrão)
uv run memoria --texto                   # digitar/ler em vez de falar/ouvir
uv run memoria --contexto closed_book    # braço sem recuperação
uv run memoria --texto --server.port 8502   # opções extras vão para o streamlit
uv run memoria --help

uv run python -m scripts.check_modes     # confere que os braços diferem só na instrução
```
