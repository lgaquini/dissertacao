# Dissertação — Memória

Terapia de reminiscência assistida por LLM local (RAG) em Raspberry Pi 5.

| Pasta | Conteúdo |
|-------|----------|
| [`tool/`](tool/) | Implementação da ferramenta (Python, gerenciado com `uv`). Ver [tool/README.md](tool/README.md). |
| [`text/`](text/) | Texto da dissertação em LaTeX (classe `texufpel`, bibliografia ABNT). |

## Compilar o texto

```bash
cd text
latexmk -pdf exemplo-diss.tex
```

Os arquivos auxiliares (`.aux`, `.log`, `.synctex.gz`, …) e o PDF gerado ficam fora do git.
