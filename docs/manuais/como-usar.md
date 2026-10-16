# docs/manuais/como-usar.md — Guia de personalização passo a passo

Este guia explica como transformar o template canônico no harness do seu projeto específico.
Siga na ordem. Não pule etapas.

---

## Pré-requisitos

```bash
# Verificar se Claude Code está disponível
claude --version

# Verificar uv (Python projects)
uv --version

# Verificar gh (opcional — para /to-issues com GitHub)
gh --version

# Verificar npx (para MCP Context-7)
npx --version
```

---

## Passo 1 — Clone e configure o ambiente

```bash
git clone <url-deste-template> meu-projeto
cd meu-projeto
git remote set-url origin <url-do-seu-novo-repo>

# Copie o .env
cp .env.example .env
# Edite .env com suas credenciais (NUNCA commite o .env)
```

---

## Passo 2 — O que já está protegido desde o clone

Antes de qualquer personalização, você já tem:

**Guardrails de SI (settings.json):**
- Bloqueia `rm -rf`, `docker volume rm`, `dropdb`, operações destrutivas
- Bloqueia `git push --force` e `git reset --hard`
- Hooks automáticos: ruff formata/fixa a cada edição Python

**Rules de segurança (rules/seguranca.md):**
- LGPD e PII: nunca logar, nunca expor sem mascaramento
- Banco de produção: somente leitura por padrão
- Secrets: nunca hardcoded

**Gate de qualidade:**
- Hook `Stop`: ruff + mypy + pytest rodam antes de encerrar qualquer sessão

Nada disso precisa ser configurado — já funciona no clone.

---

## Passo 3 — Inicie o fluxo guiado

```
/novo-projeto
```

O fluxo vai:
1. Perguntar sua ideia
2. Fazer o SI assessment (dados sensíveis? PII? produção?)
3. Detectar o tipo de projeto (app / pipeline / outro)
4. Criar `.claude/projetos/{slug}/STATUS.md` + `00-ideia.md`

**Para projetos de pipeline**, vai detectar automaticamente e aplicar configurações extras.

---

## Passo 4 — Entreviste a ideia

```
/grill-me
```

Sessão de entrevista para aprofundar a ideia. Quando terminar, salve:

```
harness-define
```

O `harness-define` estrutura o Q&A em `01-grill.md`. Para pipelines, aplica as 10 perguntas
obrigatórias antes de finalizar.

---

## Passo 5 — Gere o PRD e monte o harness

```
harness-design
```

Ele vai:
1. Rodar `/to-prd` para gerar `PRD.md`
2. Rodar `/harness-architect` para montar o `.claude/` específico do projeto
3. Salvar as decisões em `03-harness.md`

O `/harness-architect` é quem preenche o que você deixou vazio:
- `CLAUDE.md` com stack real e invariantes do produto
- Agentes de domínio específicos
- KBs da sua stack
- Rules específicas da stack
- `.mcp.json` com os stores reais

---

## Passo 6 — Preencha os PLACEHOLDERs do CLAUDE.md

Após o `/harness-architect`, o `CLAUDE.md` deve ter poucos `[PLACEHOLDERS]` restantes.
Revise e preencha manualmente o que o arquiteto não pôde inferir:

```bash
grep -n '\[.*\]' CLAUDE.md
```

Campos obrigatórios:
- `[SI-LGPD]` — declare se lida com dados pessoais e qual o propósito
- `[LAYOUT_DO_CODIGO]` — estrutura de diretórios do seu produto

---

## Passo 7 — Configure o MCP

Edite `.mcp.json` e substitua `[POSTGRES_CONNECTION_STRING]` pela connection string real.

O Context-7 já está configurado e funciona sem configuração adicional — é universal.

Para outros MCPs (Qdrant, MinIO, Databricks), o `/harness-architect` vai sugerir o que adicionar.

---

## Passo 8 — Crie as tasks e implemente

```
/to-tasks          # cria tasks/NN-*.md a partir do PRD
harness-build      # implementa task a task
```

O `harness-build` garante que cada task só fecha com:
- Gate verde (`/validar` — ruff + mypy + pytest)
- Revisor aprovado (`revisor-codigo`)
- Registro em `metrics/entregas.jsonl`

---

## Passo 9 — Encerre o projeto

Quando todas as tasks estiverem `done`:

```
harness-ship
```

Gera a retrospectiva em `05-retro.md`, fecha o `STATUS.md` e roda `/scorecard`.

---

## Como instalar skills adicionais de stack

Skills de stack específicas (fastapi-templates, langgraph-fundamentals, etc.) ficam fora do
canônico e são instaladas conforme necessário.

Crie um `skills-lock.json` na raiz:

```json
{
  "version": "1",
  "skills": {
    "fastapi-templates": {
      "source": "https://github.com/anthropics/anthropic-skills",
      "sourceType": "github",
      "skillPath": "fastapi-templates",
      "computedHash": ""
    }
  }
}
```

Para **descobrir** skills no catálogo aberto (skills.sh), use `/find-skills`.
Para **criar** uma skill nova específica deste projeto, use `/write-a-skill`.
Skill do ecossistema só entra no canônico se for vendorizada em `.claude/skills/` **e**
`.cursor/skills/` (espelho) e listada no `stack_map`; `/install-harness` é o único jeito
de propagar para um projeto-filho. `npx skills add -g` instala só em `~/.agents/skills`.

---

## Como criar novos KBs

Para criar uma KB de uma biblioteca (ex: LangGraph):

```
kb-architect — cria KB para LangGraph
```

O `kb-architect` vai:
1. Resolver o ID no Context-7 MCP
2. Buscar os tópicos principais (conceitos, padrões, API)
3. Criar `.claude/kb/langgraph/` com `index.md`, `concepts/`, `patterns/`
4. Atualizar o `CLAUDE.md` na seção Knowledge Base Map

Para atualizar uma KB existente (staleness > 3 meses):

```
kb-architect — audita KB de LangGraph
```

---

## Como criar novos agentes

```
agent-creator
```

O `agent-creator` entrevista você sobre o agente (propósito, triggers, tools, comportamento),
gera o `.md` completo com frontmatter correto e salva em `.claude/agents/`.

---

## Como usar o Caveman (redução de tokens)

O Caveman é uma skill que comprime o output do Claude para estilo conciso/primitivo.
Instale via skills-lock.json (fonte: mattpocock/skills) e invoque quando quiser respostas
mais curtas que economizem tokens na sessão.

---

## Como usar o HANDOFF

Antes de encerrar uma sessão longa, rode:

```
/handoff
```

Cria `HANDOFF.md` na raiz com:
- O que foi feito nesta sessão
- Decisões tomadas
- Próximo passo imediato
- Estado atual das tasks

Na próxima sessão, o Claude lê o `HANDOFF.md` e retoma de onde parou.

---

## Referência rápida de comandos e agentes

| Invocação | O que faz |
|---|---|
| `/novo-projeto` | Inicia fluxo guiado (ponto de entrada) |
| `/grill-me` | Entrevista da ideia |
| `/to-prd` | Gera PRD.md |
| `/to-brd` | Gera BRD a partir do resumo do meeting-analyst |
| `/harness-architect` | Gera harness do projeto a partir do PRD |
| `/to-tasks` | Fatia PRD em tasks locais (tasks/NN-*.md) |
| `/to-issues` | Fatia PRD em GitHub Issues |
| `/validar` | Gate rápido: ruff + mypy + pytest |
| `/scorecard` | Métricas de entrega (lê metrics/entregas.jsonl) |
| `/handoff` | Cria HANDOFF.md ao encerrar sessão |
| `harness-brainstorm` | Agente: captura ideia + SI + tipo |
| `harness-define` | Agente: estrutura grill + pipeline bias |
| `harness-design` | Agente: PRD + /harness-architect |
| `harness-build` | Agente: implementa tasks com gates |
| `harness-ship` | Agente: encerra projeto com scorecard |
| `harness-iterate` | Agente: atualiza fase com cascata |
| `revisor-codigo` | Agente: revisão soft do diff |
| `kb-architect` | Agente: cria/atualiza KBs via Context-7 |
| `agent-creator` | Agente: cria novos agentes via entrevista |
