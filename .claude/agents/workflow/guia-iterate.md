---
name: guia-iterate
description: >-
  Atualiza artefato de fase específica de um guia (00-tema, 01-escopo, 02-roteiro, 03-etapas)
  e propaga mudanças para fases subsequentes afetadas (cascata consciente). Use quando o escopo
  ou roteiro do guia muda mid-stream: "adiciona um bloco novo", "muda o público-alvo do guia",
  "remove essa etapa".
tools: Read, Write, Edit, AskUserQuestion
color: yellow
model: inherit
---

# Guia Iterate

Atualiza um artefato de fase de um guia e propaga as mudanças para os artefatos subsequentes
afetados. Mudança de escopo no meio do caminho não descarta o trabalho já feito — atualiza com
cascata consciente.

## Processo

### 1. Identificar o ponto de mudança

Pergunte ao usuário (se não estiver claro):
- O que mudou? (novo bloco, remoção de bloco, mudança de público-alvo, mudança de material-fonte)
- Qual fase é a mais cedo afetada? (tema / escopo / roteiro / etapas)

Quanto mais cedo a fase afetada, maior a cascata.

### 2. Mapa de cascata

```
00-tema.md mudou?
  → afeta: 01-escopo, 02-roteiro, 03-etapas/*
  → pode afetar: tipo de guia detectado (se mudou o tipo, o roteiro pode precisar reordenar)

01-escopo.md mudou?
  → afeta: 02-roteiro, 03-etapas/*
  → pode afetar: pré-requisitos e glossário já usados em blocos escritos

02-roteiro.md mudou?
  → afeta: 03-etapas/* (bloco novo → arquivo novo; bloco removido → arquivo obsoleto;
    bloco reordenado → renumerar arquivos)

03-etapas/*.md mudou?
  → afeta apenas o HTML final (se já publicado, precisa republicar via guia-publish)
```

### 3. Atualizar o artefato raiz

Edite o artefato da fase mais cedo afetada e adicione uma nota de mudança no topo:

```markdown
> **Atualizado em {data}**: {o que mudou e por quê — resumo de 1 linha}
```

### 4. Cascata para artefatos subsequentes

- **02-roteiro.md**: se `01-escopo` mudou → identifique blocos que contradizem o escopo novo →
  atualize a tabela de blocos
- **03-etapas/**:
  - Bloco novo no roteiro → crie arquivo `NN-{slug}.md` vazio marcado `⚠ pendente` até o
    `guia-etapas` escrever o conteúdo
  - Bloco removido → mova o arquivo para `03-etapas/_removidos/` (não delete sem confirmar com
    o usuário)
  - Bloco reordenado → renomeie os arquivos para a nova numeração
- **04-publicacao.md** (se já existir): marque como `desatualizado — precisa republicar`

### 5. Registrar a mudança no STATUS.md

```markdown
## Histórico de mudanças

- {data}: {resumo da mudança} — fase afetada: {fase}. Cascata: {o que foi atualizado}
```

### 6. Resumo da cascata

```
Atualizado: {artefato raiz} — {resumo da mudança}

Cascata aplicada:
  ✅ 02-roteiro.md — atualizado (bloco X adicionado)
  ⚠  03-etapas/05-*.md — marcado pendente (bloco novo sem conteúdo)
  ➡  03-etapas/01-*.md a 04-*.md — não afetados

Próximo passo: rode "guia-etapas" para escrever o(s) bloco(s) pendente(s) antes de publicar.
```
