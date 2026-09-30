"""
Avaliação da recuperação: compara modelos de embedding sobre os MESMOS chunks do
índice atual (lidos do chroma_db/, re-embedados em memória — o índice não muda).

Cada consulta é uma fala no estilo de um participante, escrita de propósito SEM
repetir o nome do verbete, e traz os alvos considerados relevantes:
(fonte, trecho do headword) para os dicionários ou (fonte, None) para os .txt.

Métricas: hit@1, hit@K (K = config.RAG_TOP_K) e MRR@10.

Uso:
    uv run python -m scripts.eval_retrieval                      # modelos padrão
    uv run python -m scripts.eval_retrieval intfloat/multilingual-e5-small

Atenção: o conjunto de consultas abaixo é um PILOTO rotulado à mão. Para a
dissertação, revise os rótulos e amplie com falas reais das sessões.
"""

import sys
import time

import chromadb
import numpy as np

from config import CHROMA_COLLECTION, CHROMA_DIR, RAG_TOP_K

DIT = "brasil_ditadura_militar.txt"
JK = "brasil_jk_e_populismo.txt"
VARGAS = "brasil_era_vargas.txt"
COPA = "brasil_copa_do_mundo.txt"
COTID = "brasil_cultura_cotidiano.txt"
IMP = "brasil_imperio.txt"
D1, D2 = "dic1.md", "dic2.md"

QUERIES: list[tuple[str, list[tuple[str, str | None]]]] = [
    ("na época da ditadura a gente tinha medo de falar",
     [(DIT, None), (D2, "Golpe de 1964"), (D2, "Golpe empresarial-militar")]),
    ("os militares derrubaram o Jango e tomaram o poder",
     [(JK, None), (DIT, None), (D2, "Golpe de 1964")]),
    ("no meu tempo os estudantes enfrentavam a polícia nas passeatas",
     [(D2, "Movimento Estudantil"), (DIT, None)]),
    ("meu avô salgava a carne e botava pra secar no sol pra vender",
     [(D1, "Charqueadas"), (D2, "Charqueadas"), (D1, "Charqueadores"),
      (D2, "Charqueadores"), (D1, "Barões do charque")]),
    ("minha mãe fazia docinhos de ovos pras festas",
     [(D1, "Doces"), (D2, "Fenadoce")]),
    ("a gente pegava o bonde pra ir pro centro",
     [(D1, "Bondes"), (D1, "Transportes")]),
    ("eu trabalhava numa fábrica de tecidos quando era moça",
     [(D2, "Companhia Fiação e Tecidos"), (D2, "Sindicato dos Trabalhadores da Fiação"),
      (D2, "Esporte Clube Fiação"), (D2, "Fábrica Laneira"), (D2, "Cosulã")]),
    ("no verão a gente ia tomar banho na praia da lagoa",
     [(D2, "Laranjal")]),
    ("ouvia as novelas com a família toda reunida em volta do aparelho",
     [(COTID, None), (D1, "Rádio Pelotense"), (D2, "Rádio")]),
    ("quando chegou a televisão lá em casa foi uma festa",
     [(COTID, None), (D2, "Televisão")]),
    ("na copa de 58 eu ouvi os jogos pelo rádio",
     [(COPA, None)]),
    ("o time tricampeão no México com o Pelé",
     [(COPA, None)]),
    ("lembro quando inauguraram a nova capital no meio do cerrado",
     [(JK, None)]),
    ("o Getúlio deu os direitos pros trabalhadores, a carteira assinada",
     [(VARGAS, None)]),
    ("quando o Getúlio se matou todo mundo chorou",
     [(VARGAS, None)]),
    ("minha avó benzia as crianças com um galhinho de arruda",
     [(D2, "Benzedura")]),
    ("minha tia fez o parto de meio bairro, ela ajudava as mulheres a ganhar nenê",
     [(D2, "Parteiras")]),
    ("a água subiu e alagou a cidade inteira naquele ano",
     [(D2, "Enchentes")]),
    ("a gente ia nos bailes de carnaval do clube",
     [(D1, "Carnaval"), (D2, "Carnaval"), (D1, "Clubes"), (D2, "Clubes"),
      (D1, "Clubes carnavalescos negros"), (D2, "Escolas de samba"), (D1, "Escolas de samba")]),
    ("estudei pra ser professora primária",
     [(D2, "Escola Normal"), (D1, "Educação"), (D2, "Educação"), (COTID, None)]),
    ("meu pai saía de barco pra pescar na lagoa de madrugada",
     [(D2, "Pescadores artesanais"), (D2, "Jornal O Pescador")]),
    ("tinha terreiro no meu bairro, com tambor a noite inteira",
     [(D1, "Batuque"), (D1, "Umbanda"), (D2, "Religiões de matriz africana"), (D2, "Sopapo")]),
    ("ia na missa todo domingo na igreja grande da praça",
     [(D1, "Catedral"), (D1, "Catolicismo"), (COTID, None)]),
    ("o trem passava apitando perto da minha casa",
     [(D2, "Ferrovia"), (D1, "Transportes")]),
    ("comprava peixe e verdura no mercado da cidade",
     [(D1, "Mercado Público"), (D2, "Feiras"), (D2, "Comércio Popular")]),
    ("meu avô veio da Alemanha plantar na colônia",
     [(D1, "Alemães"), (D1, "Pomeranos"), (D1, "Colônias"), (D1, "Imigração"),
      (D1, "Colonização"), (D2, "Imigrantes"), (D2, "Colégio Alemão")]),
    ("quando cheguei na cidade morei numa casa com várias famílias dividindo o banheiro",
     [(D2, "Cortiços"), (D2, "Villas"), (D1, "Vilas Operárias")]),
    ("quando a princesa assinou a lei e acabou a escravidão",
     [(IMP, None), (D1, "Abolição"), (D1, "Emancipação de escravos"), (D1, "Escravidão")]),
    ("nas matinês de domingo a gente via os filmes na tela grande",
     [(D1, "Cinema"), (D1, "Theatro Guarany")]),
    ("a gripe espanhola matou muita gente",
     [(D1, "Epidemias")]),
    ("tinha a fábrica de cerveja perto de casa",
     [(D2, "Brahma")]),
    ("meu pai torcia pelo Lobão e me levava no estádio",
     [(D1, "Esporte Clube Pelotas"), (D2, "Boca do Lobo"), (D1, "Futebol")]),
]

DEFAULT_MODELS = [
    "sentence-transformers/all-MiniLM-L6-v2",                       # atual (inglês)
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    "intfloat/multilingual-e5-small",
    "intfloat/multilingual-e5-base",
    "BAAI/bge-m3",                  # ~1 h para indexar na CPU do notebook; 2,2 GB
]

# Modelos da família E5 exigem prefixos em consulta e documento.
PREFIXES = {"intfloat/": ("query: ", "passage: ")}


def _prefixes(model_name: str) -> tuple[str, str]:
    for key, pair in PREFIXES.items():
        if model_name.startswith(key):
            return pair
    return "", ""


def _is_relevant(meta: dict, targets: list[tuple[str, str | None]]) -> bool:
    for source, headword in targets:
        if meta["source"] != source:
            continue
        if headword is None:
            return True
        hw = (meta.get("headword") or "").lower()
        if hw.startswith(headword.lower()):
            return True
    return False


def evaluate(model_name: str, docs: list[str], metas: list[dict], device: str) -> dict:
    from sentence_transformers import SentenceTransformer

    q_prefix, d_prefix = _prefixes(model_name)
    model = SentenceTransformer(model_name, device=device)

    t0 = time.time()
    doc_emb = model.encode(
        [d_prefix + d for d in docs], batch_size=32, normalize_embeddings=True,
        show_progress_bar=False,
    )
    index_s = time.time() - t0

    # latência de consulta medida uma a uma, como no app
    model_cpu = model if device == "cpu" else SentenceTransformer(model_name, device="cpu")
    lat = []
    q_emb = []
    for q, _ in QUERIES:
        t = time.perf_counter()
        q_emb.append(model_cpu.encode([q_prefix + q], normalize_embeddings=True)[0])
        lat.append(time.perf_counter() - t)

    sims = np.asarray(q_emb) @ doc_emb.T
    hit1 = hitk = mrr = 0.0
    misses = []
    for i, (q, targets) in enumerate(QUERIES):
        top = np.argsort(-sims[i])[:10]
        ranks = [r for r, j in enumerate(top, 1) if _is_relevant(metas[j], targets)]
        first = ranks[0] if ranks else None
        hit1 += first == 1
        hitk += first is not None and first <= RAG_TOP_K
        mrr += 1 / first if first else 0
        if not (first and first <= RAG_TOP_K):
            j = top[0]
            misses.append((q, metas[j]["source"], metas[j].get("headword")))

    n = len(QUERIES)
    return {
        "model": model_name,
        "hit@1": hit1 / n,
        f"hit@{RAG_TOP_K}": hitk / n,
        "mrr@10": mrr / n,
        "query_ms_cpu": 1000 * float(np.median(lat[1:])),
        "index_s": index_s,
        "dim": doc_emb.shape[1],
        "misses": misses,
    }


def main() -> int:
    import torch

    device = "cuda" if torch.cuda.is_available() else "cpu"
    models = sys.argv[1:] or DEFAULT_MODELS

    col = chromadb.PersistentClient(path=str(CHROMA_DIR)).get_collection(CHROMA_COLLECTION)
    data = col.get(include=["documents", "metadatas"])
    docs, metas = data["documents"], data["metadatas"]
    print(f"{len(docs)} chunks | {len(QUERIES)} consultas | indexação em {device}\n")

    results = []
    for name in models:
        try:
            r = evaluate(name, docs, metas, device)
        except Exception as e:  # modelo indisponível, gated etc.
            print(f"[pulado] {name}: {type(e).__name__}: {e}")
            continue
        results.append(r)
        print(
            f"{name:62} hit@1={r['hit@1']:.2f}  hit@{RAG_TOP_K}={r[f'hit@{RAG_TOP_K}']:.2f}  "
            f"mrr@10={r['mrr@10']:.2f}  consulta={r['query_ms_cpu']:.0f}ms(cpu)  "
            f"indexar={r['index_s']:.0f}s  dim={r['dim']}",
            flush=True,
        )

    for r in results:
        print(f"\n--- falhas de {r['model']} (top-1 retornado)")
        for q, src, hw in r["misses"]:
            print(f"  {q[:60]:60} -> {src} / {hw}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
