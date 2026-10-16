# Mapa stack → artefato

Lente para o passo 1: leia o PRD **por camada** e, para cada camada que o PRD realmente prevê,
derive os artefatos abaixo. Camada ausente no PRD **não vira arquivo**. Mantenha cada regra curta e
path-scoped; um `agent` só nasce quando há trabalho delegável de contexto fresco.

| Camada | `rules/` típico (curto, por área) | `agents/` (só se houver delegação) |
|---|---|---|
| **Backend / API** | framework async, service layer (rotas finas), contrato de erro, teste por rota — ver `kb/fastapi/` | — (o fluxo principal costuma bastar) |
| **Frontend** | framework, estado/dados, sem PII em URL/query, estados de loading/erro | — |
| **DB / dados** | separação de schemas, somente-leitura onde exigido, guardrails de query, migrations sob revisão humana | — |
| **Vetorial / RAG** | coleções por intenção, contrato de payload/metadata, filtro obrigatório, coleção escolhida pelo nó (não pelo LLM) — ver `rules/rag.md` (10 invariantes) + `kb/rag/` | `rag-architect`: design de retrieval do zero (entrevista→pipeline); `search-strategy-advisor`: qual canal para cada dado (RAG/LEDGER/MCP/híbrido) |
| **LEDGER / Busca exata** | dados exatos (ID, preço, CPF, data, saldo) vão para SQL/KV, nunca para vetor; query sempre parametrizada; allowlist de tabelas | — |
| **IA / agente** | topologia do grafo, onde o LLM decide (escopo fechado), contrato de tool, grounding — ver `rules/langgraph.md` (5 invariantes) + `kb/langgraph/` | `tool-use-evaluator`: valida uso de tools/guardrails na trajetória; `prompt-engineer`: projeta e otimiza prompts (extração, few-shot, COT, structured output) |
| **Ingestão** | pipeline offline determinístico, contrato de metadata, sem LLM raciocinando | — |
| **Evals (EDD)** | golden dataset versionado fora do backend, métricas, gate de aceite | `eval-runner`: roda a suíte e devolve só o veredito |

## Utilitários transversais (não ligados a camada de stack)

| Artefato | Tipo | Quando usar |
|---|---|---|
| `codebase-explorer` | agent | Onboarding em repo desconhecido; "o que esse projeto faz?"; mapear entry points, routers, serviços, testes |
| `sync-context` | skill | Detectar drift entre CLAUDE.md/HANDOFF.md/CONTEXT.md e código real; sincronizar após mudanças grandes |
| `make-readme` | skill | Gerar README.md a partir de CLAUDE.md + docker-compose + .env.example + ADRs — nunca inventa |
| `guia-architect` (fluxo `/novo-guia`) | skill + agents `workflow/guia-*` | Criar guia passo-a-passo didático (HTML autocontido) sobre qualquer assunto técnico — onboarding, tutorial de implementação, migração; consome `kb/design-instrucional/` + KBs técnicos do assunto via JIT |

## Regras de bolso

- **Uma rule por área, curta.** Se uma invariante forte vale para várias áreas, ela sobe pro
  `CLAUDE.md` (não se repete em cada rule).
- **Agent só com motivo.** Contexto fresco para não poluir o principal (rodar evals, validar
  trajetória, revisar). Não crie agent "porque sim" — começar mínimo.
- **Simples por padrão.** Gere o baseline de um time real (ADRs, EDD, rules, gate), mas o menor que
  cobre os riscos do PRD. Não transforme um projeto pequeno num harness "enterprise".
- **Cada artefato declara, no topo, qual pergunta responde** e quem o consome.