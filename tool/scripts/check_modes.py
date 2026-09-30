"""
Verificação dos braços experimentais — não requer Ollama, microfone nem áudio.

Confere que:
  1. cada modo monta o system prompt esperado;
  2. a ÚNICA diferença entre os prompts é a instrução de conhecimento;
  3. closed_book não recupera nada;
  4. closed_book não importa sentence_transformers/torch — verificado em
     SUBPROCESSO, porque num mesmo processo o braço rag já teria carregado
     esses módulos e o teste daria falso positivo.

Também reporta a assimetria de orçamento de contexto entre os braços, que é
confundidor a controlar no protocolo.

Uso:
    uv run python -m scripts.check_modes
"""

import difflib
import json
import os
import subprocess
import sys

from config import CONTEXT_MODES
from context import build_context, retrieval_enabled
from llm.chat import build_system_prompt

FALA = "eu morava no interior de São Paulo nos anos 60"
PESADOS = ("sentence_transformers", "torch", "chromadb")

_SNIPPET = """
import json, sys
from context import build_context
ctx, chunks = build_context({fala!r}, "closed_book")
print(json.dumps({{
    "ctx": len(ctx),
    "chunks": len(chunks),
    "heavy": [m for m in {pesados!r} if m in sys.modules],
}}))
"""


def check_import_isolation() -> list[str]:
    """Roda closed_book sozinho num processo limpo e devolve as falhas."""
    env = {**os.environ, "MEMORIA_CONTEXT_MODE": "closed_book"}
    proc = subprocess.run(
        [sys.executable, "-c", _SNIPPET.format(fala=FALA, pesados=PESADOS)],
        capture_output=True,
        text=True,
        env=env,
    )
    if proc.returncode != 0:
        return [f"subprocesso closed_book falhou:\n{proc.stderr.strip()}"]

    data = json.loads(proc.stdout.strip().splitlines()[-1])
    print(f"\n=== closed_book em processo isolado ===")
    print(f"contexto (chars)  : {data['ctx']}")
    print(f"chunks recuperados: {data['chunks']}")
    print(f"módulos pesados   : {data['heavy'] or 'nenhum'}")

    falhas = []
    if data["ctx"] or data["chunks"]:
        falhas.append("closed_book retornou contexto — não deveria")
    if data["heavy"]:
        falhas.append(
            f"closed_book importou {data['heavy']} — anula a comparação de latência"
        )
    return falhas


def main() -> int:
    prompts: dict[str, str] = {}
    falhas: list[str] = []

    for mode in CONTEXT_MODES:
        contexto, chunks = build_context(FALA, mode)
        prompts[mode] = build_system_prompt(mode, contexto)

        print(f"\n=== {mode} ===")
        print(f"recuperação ativa : {retrieval_enabled(mode)}")
        print(f"chunks recuperados: {len(chunks)}")
        print(f"contexto (chars)  : {len(contexto)}")
        print(f"prompt (chars)    : {len(prompts[mode])}")

    falhas += check_import_isolation()

    print("\n=== diferença entre os prompts (ignorando o bloco de contexto) ===")
    base = {
        m: p.split("\n\nCONTEXTO HISTÓRICO")[0].splitlines()
        for m, p in prompts.items()
    }
    a, b = CONTEXT_MODES[0], CONTEXT_MODES[1]
    diff = [
        l
        for l in difflib.unified_diff(base[a], base[b], lineterm="", n=0)
        if l.startswith(("+", "-")) and not l.startswith(("+++", "---"))
    ]
    for line in diff:
        print(line)

    if len(diff) != 2:
        falhas.append(
            f"esperava exatamente 1 linha trocada entre os braços, "
            f"encontrei {len(diff) // 2}"
        )

    print("\n=== assimetria de orçamento de contexto ===")
    delta = len(prompts["rag"]) - len(prompts["closed_book"])
    print(f"rag - closed_book : {delta} chars (~{delta // 4} tokens)")
    print("Confundidor a controlar ou reportar no protocolo.")

    print()
    if falhas:
        for f in falhas:
            print(f"FALHA: {f}")
        return 1
    print("OK — os dois braços diferem apenas na instrução de conhecimento.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
