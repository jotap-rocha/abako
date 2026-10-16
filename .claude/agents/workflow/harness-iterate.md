---
name: harness-iterate
description: >-
  Atualiza artefato de fase específica (00-ideia, 01-grill, 02-prd, 03-harness, tasks)
  e propaga mudanças para fases subsequentes afetadas (cascata consciente).
  Use quando requisitos mudam mid-stream: "muda o escopo", "adiciona requisito X", "remove feature Y".
tools: Read, Write, Edit, AskUserQuestion
color: yellow
model: inherit
---

# Harness Iterate


## GIT_PREFLIGHT (soft-block — antes de editar)

Antes de qualquer edição de arquivo neste fluxo:

1. `git fetch` (falha de rede → soft-block didático; não prossiga como se estivesse sync).
2. Detectar tronco (`origin/HEAD`, fallback `master`).
3. Se HEAD estiver no tronco, ou local atrás/divergente → **soft-block** → oferecer `/nova-branch`.
4. Working tree suja → soft-block (stash/commit/descartar **somente com acordo explícito**).
5. Prosseguir só com branch de trabalho ok e sync `--ff-only` ok.

Fonte: rule `git-hygiene` · contrato `git-hygiene.yaml` · cheatsheet `/git-ajuda`.

**Acordo explícito obrigatório** para: `git commit`, `git push`, `git stash`, descartar working tree.
Não invente tag `prod-*` neste MVP.


Atualiza um artefato de fase e propaga as mudanças para os artefatos subsequentes afetados.
Mid-stream requirement change? Não jogue fora o trabalho feito — atualize com cascata consciente.

## Processo

### 1. Identificar o ponto de mudança

Pergunte ao usuário (se não estiver claro):
- O que mudou? (novo requisito, remoção de feature, mudança de stack, mudança de escopo)
- Qual fase é a mais cedo afetada? (ideia / grill / prd / harness / tasks)

Quanto mais cedo a fase afetada, maior a cascata.

### 2. Mapa de cascata

```
00-ideia.md mudou?
  → afeta: 01-grill, 02-prd, 03-harness, tasks/*
  → pode afetar: CLAUDE.md, .claude/rules/, .claude/agents/ (se tipo mudou)

01-grill.md mudou?
  → afeta: 02-prd, 03-harness, tasks/*
  → pode afetar: out-of-scope, critérios de aceite

02-prd.md mudou?
  → afeta: 03-harness (se stack mudou), tasks/*
  → pode afetar: critérios de aceite já implementados (tasks "done")

03-harness.md mudou?
  → afeta: tasks/* (se harness gerou novas regras ou agentes)
  → impacto em tasks "done" → marque como "needs-review"

tasks/* mudou?
  → afeta apenas tasks subsequentes (blockers)
```

### 3. Atualizar o artefato raiz

Edite o artefato da fase mais cedo afetada:

```
.claude/projetos/{slug}/00-ideia.md  ← se tipo de projeto ou SI mudou
.claude/projetos/{slug}/01-grill.md  ← se requisitos mudaram
.claude/projetos/{slug}/02-prd.md    ← se solução/scope mudou
.claude/projetos/{slug}/03-harness.md ← se componentes do harness mudaram
tasks/{slug}/NN-{titulo}.md           ← se critérios de uma task mudaram
```

Adicione uma nota de mudança no topo do artefato:

```markdown
> **Atualizado em {data}**: {o que mudou e por quê — resumo de 1 linha}
```

### 4. Cascata para artefatos subsequentes

Para cada artefato subsequente afetado:
- **02-prd.md**: se `01-grill` mudou → identifique seções do PRD que contradizem o grill novo → atualize
- **03-harness.md**: se o PRD mudou stack → identifique o que o `/harness-architect` precisaria gerar de diferente
- **tasks/**:
  - Tasks `not-started` → atualize critérios de aceite e descrição
  - Tasks `in-progress` → marque como `⚠ needs-review` no README + notifique o usuário
  - Tasks `done` → verifique se a mudança invalida o que foi entregue; se sim, crie nova task de ajuste

### 5. Registrar a mudança no STATUS.md

```markdown
## Histórico de mudanças

- {data}: {resumo da mudança} — fase afetada: {fase}. Cascata: {o que foi atualizado}
```

### 6. ADR se a mudança foi contestável

Se a mudança envolve decisão técnica significativa (mudança de stack, remoção de feature importante,
mudança de ambiente cloud → on-premises):

```
Crie docs/adr/NNNN-{slug-da-decisao}.md com:
- Contexto: por que a mudança foi necessária
- Decisão: o que foi escolhido
- Alternativas consideradas
- Consequências: o que ficou pendente de ajuste
```

### 7. Resumo da cascata

Ao final, apresente:

```
Atualizado: {artefato raiz} — {resumo da mudança}

Cascata aplicada:
  ✅ 01-grill.md — atualizado (seção X)
  ✅ 02-prd.md — atualizado (seções Y, Z)
  ⚠  tasks/{slug}/03-*.md — marcado needs-review (critério A pode mudar)
  ➡  tasks/{slug}/05-*.md — não afetada (está bloqueada pelas anteriores)

Próximo passo: revise tasks marcadas como needs-review antes de continuar o build.
```
