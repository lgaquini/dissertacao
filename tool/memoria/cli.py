"""
Atalho para subir a interface: `uv run memoria`.

Exemplos (a partir de tool/):
    uv run memoria                          # voz + rag
    uv run memoria --texto                  # digitar/ler na tela
    uv run memoria --contexto closed_book
    uv run memoria --texto --server.port 8502   # opções extras vão para o streamlit

O streamlit roda num processo filho com as variáveis MEMORIA_* definidas, porque
config.py lê o ambiente no import — e este launcher já importou config para
validar as opções.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

from config import CONTEXT_MODE, CONTEXT_MODES, INTERFACE_MODE, INTERFACE_MODES

# Funciona com a instalação editável que o `uv sync` faz: o pacote aponta para
# tool/, onde estão main.py e .streamlit/config.toml.
APP_DIR = Path(__file__).resolve().parent.parent


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="memoria",
        description="Sobe a interface da Memória (streamlit run main.py).",
    )
    parser.add_argument(
        "--interface",
        choices=INTERFACE_MODES,
        default=INTERFACE_MODE,
        help=f"modo de interação (padrão: {INTERFACE_MODE})",
    )
    parser.add_argument(
        "--texto",
        dest="interface",
        action="store_const",
        const="texto",
        help="atalho para --interface texto",
    )
    parser.add_argument(
        "--contexto",
        choices=CONTEXT_MODES,
        default=CONTEXT_MODE,
        help=f"braço experimental (padrão: {CONTEXT_MODE})",
    )
    args, streamlit_args = parser.parse_known_args()

    env = {
        **os.environ,
        "MEMORIA_INTERFACE_MODE": args.interface,
        "MEMORIA_CONTEXT_MODE": args.contexto,
    }
    print(f"[memoria] interface={args.interface} contexto={args.contexto}", flush=True)

    cmd = [sys.executable, "-m", "streamlit", "run", "main.py", *streamlit_args]
    try:
        # cwd=APP_DIR para o streamlit achar .streamlit/config.toml (tema).
        return subprocess.call(cmd, cwd=APP_DIR, env=env)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
