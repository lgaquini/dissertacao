# TODO — Roadmap de Implementação

> Projeto "Memória" — terapia de reminiscência assistida por LLM local em Raspberry Pi 5.

**Princípio de ordenação:** o que bloqueia a dissertação vem antes do que bloqueia o produto.
Robustez é construída *depois* de observar falhas reais em sessão, não antes.

**Esforço:** `P` = até 2h · `M` = meio dia a 2 dias · `G` = 3+ dias
Todo item tem critério de aceite verificável. Item sem aceite não entra na lista.

---

## Fase 0 — Caminho crítico da dissertação

> Bloqueia coleta de dados. Começar hoje, em paralelo com o resto.

### 0.1 Submissão ao CEP / Plataforma Brasil `G`
- [ ] Redigir protocolo de pesquisa, TCLE e termo de assentimento por procurador (participantes com possível comprometimento cognitivo).
- [ ] Definir critérios de inclusão/exclusão e recrutamento.
- [ ] Submeter e acompanhar parecer.
- ✅ **Aceite:** protocolo submetido com número CAAE; nenhuma sessão com participante real antes do parecer aprovado.
- ⚠️ Prazo institucional de meses. É o item de maior lead time do projeto.

### 0.2 Política de dados e LGPD `M`
- [x] Decidir: o áudio bruto é descartado após transcrição ou retido? (recomendação: descartar após transcrição).
- [X] Definir janela de retenção, local de armazenamento e pseudonimização de transcrições.
- [X] Documentar quem tem acesso e como o participante solicita exclusão.
- ✅ **Aceite:** política escrita de uma página, refletida no TCLE e implementada no código antes de qualquer log persistente (ver 5.1).
- O áudio será descartado!

### 0.3 Protocolo de avaliação e métricas `M`
- [ ] Definir desfecho primário e secundários. Candidatos: duração da conversa, nº de turnos, riqueza autobiográfica (nº de eventos de vida evocados), variação de sentimento pré/pós.
- [ ] Escolher instrumentos: GDS-15, QMMI, escala de engajamento.
- [ ] **Definir condição controle.** Sem baseline não há como atribuir efeito ao RAG. Opções: (a) mesmo sistema sem RAG, (b) prompts de reminiscência em papel, (c) within-subject A/B por sessão.
- ✅ **Aceite:** documento com desfechos, instrumentos, condição controle e tamanho de amostra pretendido — aprovado pela orientação antes de instrumentar código.

### 0.4 Orçamento de latência `M`
- [ ] Instrumentar tempo por etapa: gravação → STT → retrieval → LLM → TTS → áudio audível.
- [ ] Medir no Pi 5 real, não na máquina de desenvolvimento.
- [ ] Definir alvo (sugestão: ≤ 4s do fim da fala ao início da resposta falada) e registrar o que a configuração atual entrega.
- ✅ **Aceite:** tabela de latência p50/p95 por etapa, medida no Pi, versionada no repositório. Toda mudança de modelo ou pipeline atualiza a tabela.
- 💡 É a variável que decide se o sistema parece uma companhia ou um quiosque. Medir antes de otimizar qualquer coisa.

### 0.5 Taxa de alucinação histórica `M`
- [ ] Amostrar N respostas, verificar cada fato histórico afirmado contra o corpus e contra fonte externa.
- [ ] Classificar: fato correto e ancorado no contexto / correto mas não ancorado / incorreto.
- ✅ **Aceite:** taxa medida e reportada. É métrica de segurança *e* resultado publicável — o prompt instrui a nunca corrigir a pessoa, então o sistema não pode ser ele mesmo a fonte do erro.

---

## Fase 1 — Correções de bugs

> Barato, alto impacto, tudo verificado no código atual. Fazer antes de qualquer feature.

### 1.1 Estouro da janela de contexto `M` 🔴
- [ ] `LLM_NUM_CTX = 2048` mas o consumo fixo já é ~1000 tokens: system prompt (~400) + 4 chunks × 500 chars (~600). O histórico completo é reenviado a cada turno (`llm/chat.py`), e o Ollama trunca em silêncio por volta do turno 8.
- [ ] Corrigir com: (a) contar tokens e avisar, (b) janela deslizante de histórico, (c) sumarização incremental (ver 2.2), (d) avaliar aumento de `num_ctx` medindo o custo em latência.
- ✅ **Aceite:** conversa de 20 turnos sem truncamento silencioso; o system prompt nunca é descartado; latência p95 dentro do alvo de 0.4.
- 💡 Conversas longas são o desfecho primário da intervenção. Este é o bug mais importante do projeto.

### 1.2 TTS emudece se o Piper faltar `P` 🔴
- [ ] `main.py` faz `if piper_available(): speak(...)`, mas `speak()` tenta edge-tts *primeiro*. Se o `.onnx` do Piper não existir num Pi novo, o sistema fica **totalmente mudo, sem erro** — mesmo com edge-tts funcionando.
- [ ] Inverter: sempre chamar `speak()`; deixar a cadeia de fallback decidir; sinalizar na UI se nenhum backend respondeu.
- ✅ **Aceite:** removendo `models/piper/*.onnx`, o sistema continua falando via edge-tts. Sem rede *e* sem Piper, a UI informa que está em modo texto.

### 1.3 30 segundos de silêncio para quem hesita `P` 🔴
- [ ] Em `audio/stt.py`, `record_until_silence` só corta cedo depois que `speaking_started` vira True. Um participante idoso que pausa antes de falar grava os 30s inteiros e depois espera o Whisper transcrever silêncio.
- [ ] Adicionar timeout de "ninguém falou ainda" (sugestão: 6s) com mensagem acolhedora e novo convite.
- ✅ **Aceite:** botão pressionado sem fala nenhuma retorna em ≤ 7s com convite para tentar de novo.

### 1.4 Portão de confiança no RAG `P`
- [ ] `distance` já é calculada e exibida no debug, mas nunca usada. Se a menor distância exceder o limiar, suprimir o bloco de contexto naquele turno.
- [ ] Calibrar o limiar com queries reais antes de fixá-lo.
- ✅ **Aceite:** query fora de domínio ("qual a capital da Mongólia") não injeta contexto histórico; limiar documentado com as queries que o calibraram.

### 1.5 Query de recuperação construída da fala crua `M`
- [ ] `retrieve_raw(user_text)` com `user_text = "morava lá, sim"` recupera ruído.
- [ ] Reescrever/expandir a query usando os últimos turnos antes de embeddar.
- ✅ **Aceite:** conjunto de 20 falas curtas reais; a reescrita melhora a relevância do top-1 em avaliação manual comparada à baseline.
- 💡 Ganho maior que re-ranker, num corpus de 68 KB (~150 chunks).

### 1.6 Escapar HTML das falas `P`
- [ ] `_history_html` interpola conteúdo do LLM em `unsafe_allow_html=True`. Um `<` na resposta quebra o layout.
- [ ] `html.escape()` em fala do usuário e do assistente.
- ✅ **Aceite:** resposta contendo `<b>` e `&` renderiza como texto literal.

### 1.7 Saída de áudio: config morta e exceção não tratada `P`
- [ ] `AUDIO_OUTPUT_DEVICE` está em `config.py` e nunca é lido.
- [ ] `_play` fixa `paplay` com `check=True` → exceção não tratada num Pi sem PulseAudio.
- [ ] Honrar a config e degradar para `aplay` antes de desistir.
- ✅ **Aceite:** com PulseAudio parado, o áudio sai por `aplay` ou a falha aparece como aviso, não como traceback.

---

## Fase 2 — Qualidade da conversa

### 2.1 Prompts versionados em arquivo + few-shot `M`
- [ ] Extrair `SYSTEM_PROMPT` de `config.py` para `prompts/*.md` versionados.
- [ ] Adicionar 2–3 exemplos few-shot do formato desejado (curto, empático, uma pergunta aberta).
- [ ] Padronizar a regra de formato (o prompt diz "2-3 frases + 1 pergunta" — usar essa redação em todo lugar).
- ✅ **Aceite:** trocar de variante de prompt sem editar código; em 20 respostas amostradas, ≥ 90% terminam em pergunta aberta e têm ≤ 3 frases.
- 💡 Few-shot é preferível a validar-e-repromptar: repromptar dobra a latência no pior caso, num Pi que já é o gargalo.

### 2.2 Sumarização e persistência da sessão `M`
- [ ] Comprimir periodicamente o histórico preservando fatos biográficos.
- [ ] Persistir a conversa fora do `session_state` do Streamlit para permitir retomada — respeitando a política de 0.2.
- ✅ **Aceite:** reiniciar o app retoma a conversa anterior com os fatos biográficos intactos; resolve conjuntamente 1.1.

### 2.3 Perfil persistente do participante `M`
- [ ] Armazenar nome, cidade de origem, época da juventude, eventos de vida e familiares citados.
- [ ] Usar na personalização das perguntas de sessões futuras.
- ✅ **Aceite:** na segunda sessão o sistema referencia espontaneamente um fato dado na primeira.

### 2.4 Detecção de angústia `M`
- [ ] Detectar tristeza, raiva ou retraimento — **como campo estruturado da mesma chamada ao LLM**, sem adicionar um modelo ao Pi.
- [ ] Ao detectar, mudar o tom para conforto e sugerir envolvimento do cuidador.
- [ ] Consentimento explícito antes de iniciar gravação (requisito de 0.1, não item de UX).
- ✅ **Aceite:** conjunto de falas de teste rotuladas; o sinal dispara nos casos rotulados sem custo de latência mensurável.

---

## Fase 3 — Qualidade da recuperação

### 3.1 Chunking semântico `M`
- [ ] Trocar corte por caractere fixo (`rag/ingest.py`) por limites de sentença/parágrafo.
- [ ] Adicionar metadados temporais (década, período histórico) aos chunks para filtro ou boosting por época.
- ✅ **Aceite:** nenhum chunk começa ou termina no meio de uma frase; filtro por década funcional no debug.
- 💡 Importa mais que re-ranking num corpus pequeno.

### 3.2 Diversificar o corpus `M`
- [ ] Expandir `data/historia/` com cultura pop por década, música, esportes, tecnologia do cotidiano, preços de época, história local/regional.
- ✅ **Aceite:** o corpus cobre as décadas de juventude da população-alvo; medir se a recuperação melhora nas queries que hoje falham.
- 💡 Hoje são 68 KB, quase todo de história política. Reminiscência vive do cotidiano, não de datas de governo.

### 3.3 Busca híbrida esparsa+densa `M` — condicional
- [ ] **Só fazer se 1.5 e 3.1 não resolverem.** Adicionar BM25/TF-IDF para nomes próprios, datas e locais.
- ✅ **Aceite:** existe um conjunto documentado de queries de nome próprio que a busca densa erra e a híbrida acerta. Sem esse conjunto, não implementar.

---

## Fase 4 — UX e acessibilidade

### 4.1 Mensagens de erro terapêuticas `P`
- [ ] Trocar "Não consegui entender. Tente falar mais próximo do microfone." por acolhimento ("Não ouvi direito, pode repetir?").
- ✅ **Aceite:** nenhuma string voltada ao participante usa vocabulário técnico ou culpa a pessoa.

### 4.2 Modo alto contraste e fonte grande `M`
- [ ] Alternativa ao estilo jornalístico atual, comutável na UI.
- ✅ **Aceite:** contraste ≥ 4.5:1 (WCAG AA); corpo de texto ajustável até 1.5× sem quebrar layout.

### 4.3 Feedback sonoro de gravação `P`
- [ ] Beeps discretos no início e fim da captura, para participantes com baixa visão.
- ✅ **Aceite:** o participante identifica o estado de gravação sem olhar a tela.

### 4.4 Ritmo da fala ajustável `P`
- [ ] Expor velocidade do TTS (edge-tts e Piper) em configuração.
- ✅ **Aceite:** fala 20% mais lenta selecionável, sem distorção.

### 4.5 Pré-processamento de áudio `M`
- [ ] Supressão de ruído e normalização antes do Whisper.
- [ ] Tornar o limiar de silêncio adaptativo — o `0.01` fixo não serve para toda voz nem todo ambiente.
- ✅ **Aceite:** em ambiente com ruído de fundo, a taxa de erro de palavra não piora em relação ao ambiente silencioso além de um limite definido.

---

## Fase 5 — Robustez orientada por falhas observadas

> Escopo deliberadamente reduzido. Implementar **apenas** as cadeias correspondentes a falhas
> que realmente ocorreram em sessão registrada. Cadeia hipotética não entra.

### 5.1 Logging estruturado `M`
- [ ] JSONL com: chamada ao LLM, chunks recuperados, transcrição, saída TTS, latência por etapa, sinal de angústia, ação de recuperação.
- [ ] **Depende de 0.2.** Registrar o mínimo necessário para as métricas de 0.3 — não "tudo".
- ✅ **Aceite:** as métricas de 0.3 e 0.4 são extraíveis do log sem instrumentação adicional; nada além do previsto na política de dados é gravado.

### 5.2 Fallbacks pontuais `M`
- [ ] Uma cadeia por falha observada. Candidatas, em ordem de probabilidade: TTS (já em 1.2), Ollama indisponível, ChromaDB vazio ou corrompido, microfone ausente.
- ✅ **Aceite:** cada fallback implementado aponta para a entrada de log da falha real que o motivou.

### 5.3 Circuit breaker `P` — condicional
- [ ] Só se 5.1 mostrar falhas repetidas e custosas no mesmo componente.
- ✅ **Aceite:** existe evidência em log de falha em cascata que o breaker teria evitado.

### 5.4 Modo seguro `M` — condicional
- [ ] Só depois de 5.2 cobrir as falhas reais. Botões grandes com conversas pré-programadas + painel para cuidador.
- ✅ **Aceite:** com Ollama, rede e microfone todos indisponíveis, o participante ainda tem uma interação digna.

---

## Não faremos

Cortes explícitos. Registrados para não voltarem por inércia.

| Item | Motivo |
|---|---|
| Cross-encoder re-ranker | Custo de latência no Pi 5 sem ganho plausível reordenando 4 de ~150 chunks. Ver 3.3 se houver evidência. |
| Corpus multilíngue (italiano, alemão, japonês) | Escopo além da dissertação. Registrar como trabalho futuro no texto. |
| Validar saída e repromptar | Dobra a latência no pior caso. Substituído por few-shot (2.1). |
| Modelo de sentimento dedicado | Resolvido como campo estruturado da chamada existente (2.4). |
| Suíte completa de health probes | Substituída por fallbacks pontuais orientados por falha observada (Fase 5). |

---

## Ordem de execução

1. **Agora, em paralelo:** 0.1 e 0.2 (lead time institucional) + toda a Fase 1 (bugs).
2. **Em seguida:** 0.3 e 0.4 — o protocolo define o que instrumentar; a latência define o que é viável.
3. **Depois:** 2.1 → 2.2 → 3.1 → 3.2, medindo latência a cada passo.
4. **Piloto interno** (sem participante externo, pré-parecer): rodar sessões completas, coletar log.
5. **Fase 5** guiada pelo que o piloto quebrou. **Fase 4** conforme o piloto revelar atrito de uso.
6. 0.5 e as métricas finais sobre a versão estabilizada.

## Rastreamento

- [ ] Documentar decisões de design e limitações éticas no texto da dissertação (contínuo).
- [ ] Atualizar a tabela de latência de 0.4 a cada mudança de modelo ou pipeline.
- [ ] Revisar este roadmap ao fim de cada fase: o que virou evidência, o que virou corte.
