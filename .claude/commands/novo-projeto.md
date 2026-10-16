---
description: >-
  Inicia o fluxo guiado de criação de projeto. Captura ideia, faz SI assessment,
  detecta tipo (app/pipeline/agente), cria .claude/projetos/{slug}/ com STATUS.md e 00-ideia.md.
  É o ponto de entrada do Agent Harness Method — rode antes de qualquer /grill-me.
---

# /novo-projeto — fluxo guiado

Este comando inicia o `harness-brainstorm` para capturar sua ideia e configurar o harness.

---

## O que acontece

```
/novo-projeto
    ↓
harness-brainstorm (agente)
    ├── Passo 0a: "Qual ideia você quer construir?"
    ├── Passo 0b: SI Assessment (a/b/c/d)
    ├── Passo 0c: Tipo de projeto (app / pipeline-local / pipeline-cloud / outro)
    ├── Deriva slug do nome
    └── Cria .claude/projetos/{slug}/STATUS.md + 00-ideia.md
```

---

## Subcomandos de checkpoint

Use estes checkpoints conforme avança no fluxo:

```bash
/novo-projeto salvar-grill     # salva Q&A do /grill-me em 01-grill.md
/novo-projeto salvar-prd       # copia PRD.md em 02-prd.md
/novo-projeto salvar-harness   # registra decisões do /harness-architect em 03-harness.md
/novo-projeto salvar-tasks     # cria 04-tasks-index.md com sumário das tasks
/novo-projeto shippar          # cria 05-retro.md + fecha STATUS.md (chame harness-ship)
```

---

## Fluxo completo pós-/novo-projeto

```
1. /novo-projeto              → 00-ideia.md criado
2. /grill-me                  → entrevista a ideia
3. harness-define             → salva em 01-grill.md
4. /to-prd                    → gera PRD.md
5. /harness-architect         → gera o .claude/ específico do projeto
6. harness-design             → salva PRD e decisões de harness
7. /to-tasks                  → cria tasks/NN-*.md
8. harness-build              → implementa task a task (gate + revisor)
9. harness-ship               → scorecard + retrospectiva + fecha
```

---

## Salvar checkpoint de grill

Quando o `/grill-me` terminar, rode:

```
/novo-projeto salvar-grill
```

O agente lê o histórico da conversa e salva o Q&A estruturado em `.claude/projetos/{slug}/01-grill.md`.

Para projetos de pipeline, inclui as **10 perguntas obrigatórias** antes de finalizar.

---

## Salvar checkpoint de PRD

Após `/to-prd` gerar `PRD.md`:

```
/novo-projeto salvar-prd
```

Copia o conteúdo para `.claude/projetos/{slug}/02-prd.md` e atualiza o STATUS.md.

---

## Salvar checkpoint de harness

Após `/harness-architect` concluir:

```
/novo-projeto salvar-harness
```

Registra em `.claude/projetos/{slug}/03-harness.md`:
- O que foi gerado (agentes, rules, KBs, skills)
- Por que cada decisão foi tomada
- O que foi personalizado vs o que já estava no canônico

---

## Salvar tasks

Após `/to-tasks` criar as tasks:

```
/novo-projeto salvar-tasks
```

Cria `.claude/projetos/{slug}/04-tasks-index.md` com sumário de todas as tasks.

---

## Shippar

Quando todas as tasks estiverem `done`:

```
/novo-projeto shippar
```

Invoca `harness-ship` para:
1. Rodar `/scorecard`
2. Escrever retrospectiva em `05-retro.md`
3. Fechar STATUS.md com resultado final

---

## Ver projeto ativo

```
cat .claude/projetos/{slug}/STATUS.md
```

Ou liste todos os projetos:

```bash
ls .claude/projetos/
```
