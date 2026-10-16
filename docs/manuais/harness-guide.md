# HARNESS-GUIDE — como trabalhar com o harness instalado

> Referência rápida para projetos que já têm o agent harness configurado.
> Para quem está clonando o template do zero, veja `docs/manuais/como-usar.md`.

---

## Git Hygiene (convenção)

- Fonte: `git-hygiene.yaml` · rule `git-hygiene` · cheatsheet `docs/cheatsheets/git-hygiene-cheatsheet.md`
- Comandos: `/nova-branch` (criar branch) · `/git-ajuda` (contrato de 1 página)
- Adapter SCM: `scm: azure | github` (detecta pelo remote; ver `docs/cheatsheets/scm-pr-hibrido.md`)
- Hooks locais: `.githooks/` + `./scripts/bootstrap-githooks.sh` (só após confirmação no install)
- Soft-block `GIT_PREFLIGHT` nos agents `harness-*` e Dev Loop — commit/push só com acordo

Declaração §1.3: sem Edit policies, nenhum gate impede de fato; objetivo = caminho certo fácil.

---

## O fluxo de trabalho

```
Fase 0           Fase 1          Fase 2              Fase 3         Fase 4
IDEIA       →   REQUISITOS   →   PRD + HARNESS   →   IMPLEMENTAR   →   ENCERRAR
brainstorm      grill-me         harness-design       to-tasks           harness-ship
                harness-define   to-prd               harness-build      /scorecard
                                 harness-architect    revisor-codigo
```

---

## Fase 0 — Capturar a ideia

```
harness-brainstorm
```

Entrevista estruturada: captura a ideia, faz SI assessment (dados sensíveis? PII? produção?),
detecta tipo de projeto (app / pipeline / agente). Cria `STATUS.md` + `00-ideia.md` em
`.claude/projetos/{slug}/`. No enter, avisa 1× como abrir o painel live
(`projetos/{slug}/fluxo/live.html` / `/fluxo-live`) — Dev Loop fora deste aviso (MVP).

---

## Fase 1 — Aprofundar requisitos

```
/grill-me
```
Sessão de entrevista para aprofundar e validar a ideia. Ao terminar:

```
harness-define
```
Estrutura o Q&A em `01-grill.md`. Para pipelines: aplica as 10 perguntas obrigatórias de
ingestão + qualidade + contrato antes de finalizar.

---

## Fase 2 — Gerar PRD e configurar o harness

```
harness-design
```
Orquestra dois passos em sequência:
1. `/to-prd` — gera `PRD.md` a partir do grill
2. `/harness-architect` — entrevista sobre stack e monta `.claude/` completo para o projeto

O `/harness-architect` preenche `CLAUDE.md` com invariantes reais, seleciona KBs, rules e
agentes de domínio, e configura `.mcp.json` com os stores do projeto.

---

## Fase 3 — Implementar

```
/to-tasks          # cria tasks/{slug}/NN-*.md a partir do PRD (sem GitHub)
/to-issues         # cria GitHub Issues (requer gh CLI)
```

Para cada task:
```
harness-build
```
Implementa a task com gate obrigatório: ruff + mypy + pytest (`/validar`) + `revisor-codigo`.
Só fecha a task quando gate verde E revisor aprovado.

---

## Fase 4 — Encerrar o projeto

```
harness-ship
```
Roda `/sync-context` (passo obrigatório — critério 7 da DoD), gera retrospectiva em
`05-retro.md`, fecha `STATUS.md`, roda `/scorecard`.

O sync não é opcional: `CLAUDE.md`, `CONTEXT.md` e `AGENTS.md` precisam descrever o código que
existe agora, não o do início do projeto. O `AGENTS.md` é derivado do `CLAUDE.md` por script —
não edite à mão.

---

## Agentes disponíveis

| Agente | O que faz | Quando usar |
|---|---|---|
| `harness-brainstorm` | Captura ideia + SI assessment + tipo de projeto | Início de todo projeto |
| `harness-define` | Estrutura grill em requisitos formais | Após `/grill-me` |
| `harness-design` | Gera PRD + monta `.claude/` via `/harness-architect` | Após requisitos aprovados |
| `harness-build` | Implementa tasks com gate verde obrigatório | Durante a implementação |
| `harness-iterate` | Atualiza fase + propaga mudanças em cascata | Quando requisito muda mid-stream |
| `harness-ship` | Sync de contexto + retrospectiva + scorecard + fecha STATUS.md | Quando todas as tasks estão done |
| `revisor-codigo` | Revisão soft do diff contra rules do projeto | Antes de commitar/abrir PR |
| `codebase-explorer` | Mapeia repo desconhecido (Executive Summary + Deep Dive) | Onboarding ou codebase nova |
| `kb-architect` | Cria, atualiza e audita domínios KB em `.claude/kb/` | Adicionar nova biblioteca ao contexto |
| `agent-creator` | Cria novos agentes via entrevista estruturada | Quando precisar de um agente customizado |
| `prompt-engineer` | Projeta, otimiza e testa prompts LLM | Extraction, geração, structured output |
| `sql-architect` | Projeta queries SQL seguras: SELECT, RLS, multi-tenant, índices | Design de queries complexas |
| `rag-architect` | Projeta sistemas RAG/LEDGER/híbrido | Qualquer feature de busca semântica |
| `search-strategy-advisor` | Recomenda estratégia: semântica vs exata vs híbrida | Antes de implementar busca |
| `meeting-analyst` | Transforma notas/transcrições em decisões + action items + ADRs | Reuniões com product/stakeholders |

---

## Skills disponíveis

| Skill (invocação) | O que faz | Quando usar |
|---|---|---|
| `/harness-architect` | Entrevista sobre stack → gera `.claude/` completo | Configurar harness de um projeto |
| `/install-harness` | Instala ou atualiza harness canônico no projeto | Bootstrap ou atualizar quando o canônico evoluiu |¹
| `/grill-me` | Entrevista relentless sobre plano ou design | Aprofundar ideia antes de virar PRD |
| `/grill-with-docs` | Grilling contra documentação de domínio existente | Preencher `CONTEXT.md` com especialista |
| `/to-prd` | Converte conversa em PRD e publica no tracker | Fechar requisitos em documento |
| `/to-brd` | Gera BRD formal a partir do resumo do `meeting-analyst` | Depois da call, com a pasta do resumo |
| `/to-tasks` | Fatia PRD em `tasks/{slug}/NN-*.md` locais (não flat na raiz) | Quando não usa GitHub Issues |
| `/to-issues` | Fatia PRD em GitHub Issues com labels e critérios | Quando usa GitHub como tracker |
| `/gen-tests` | Gera testes pytest ou vitest para módulo/função | Após implementar um módulo |
| `/new-adr` | Registra Architecture Decision Record em `docs/adr/` | Antes de commitar decisão contestável |
| `/sync-context` | Sincroniza `CLAUDE.md`/`AGENTS.md`/`CONTEXT.md` com o código real | Obrigatório no fechamento; também ao abrir sessão em repo antigo |
| `/make-readme` | Gera `README.md` a partir de CLAUDE.md + docs + compose | Quando README está desatualizado |
| `/handoff` | Compacta sessão em `HANDOFF.md` para o próximo agente | Antes de encerrar sessão longa |
| `/create-rag-pipeline` | Gera pipeline RAG completo (ingestão + query) | Feature de busca semântica do zero |
| `/search-strategy-check` | Checklist para decidir estratégia de busca correta | Antes de `/create-rag-pipeline` |
| `/write-a-skill` | Cria nova skill customizada para o projeto | Operação repetível que não tem skill |
| `/find-skills` | Descobre skills no ecossistema (`npx skills` / skills.sh) | "tem skill para X", instalar do catálogo aberto |
| `/documentation-writer` | Documentação nos quadrantes Diátaxis (tutorial, how-to, reference, explanation) | Docs além do README sintético de `/make-readme` |
| `/excalidraw-diagram` | Gera diagrama `.excalidraw` com argumentação visual + validação PNG | Visualizar arquiteturas, fluxos e conceitos |

¹ `/install-harness` também roda como **CLI standalone**, fora de uma sessão Claude Code:
`./install-harness` (launcher guiado — pergunta destino e novo/existente) ou, direto com flags,
`python3 .claude/skills/install-harness/scripts/install_harness.py <destino>`. Detecta o projeto,
mostra o Install Plan e pergunta (`input()`) antes de tocar qualquer arquivo que já exista. Veja
`docs/manuais/install-harness-cli.md`.

---

## Manutenção contínua do harness

```
/sync-context       # sincroniza CLAUDE.md / CONTEXT.md / AGENTS.md com o código real
                    # (obrigatório no ship e no EXIT_COMPLETE do Dev Loop — critério 7 da DoD;
                    #  o hook de Stop já avisa quando detecta drift)
kb-architect        # atualiza KB de biblioteca específica (> 3 meses = stale)
agent-creator       # cria agente para responsabilidade nova
/write-a-skill      # cria skill nova do harness
/find-skills        # descobre skill no catálogo aberto (skills.sh)
/new-adr            # registra decisão de arquitetura antes de implementar
/handoff            # encerra sessão longa com resumo para próximo agente
/install-harness    # propaga evoluções do canônico para este projeto
```

---

## Referência rápida

| Invocação | Propósito |
|---|---|
| `harness-brainstorm` | Fase 0: capturar ideia + SI |
| `/grill-me` | Fase 1: aprofundar requisitos |
| `harness-define` | Fase 1: estruturar em documento |
| `harness-design` | Fase 2: PRD + harness |
| `/to-prd` | Gerar PRD.md |
| `/to-brd` | Gerar BRD a partir do resumo do meeting-analyst |
| `/harness-architect` | Montar `.claude/` do projeto |
| `/to-tasks` | Fatiar em tasks locais |
| `/to-issues` | Fatiar em GitHub Issues |
| `harness-build` | Implementar com gates |
| `revisor-codigo` | Revisão antes de commitar |
| `/validar` | Gate: ruff + mypy + pytest |
| `harness-ship` | Encerrar projeto |
| `/scorecard` | Métricas de entrega |
| `/handoff` | Encerrar sessão |
| `/sync-context` | Sincronizar contexto no fechamento |
| `kb-architect` | Criar/atualizar KB |
| `agent-creator` | Criar agente novo |
| `/new-adr` | Registrar decisão |
| `/install-harness` | Atualizar harness |
| `/find-skills` | Descobrir skill no catálogo aberto (skills.sh) |
| `/excalidraw-diagram` | Gerar diagrama visual argumentativo |
