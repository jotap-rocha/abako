# .claude/projetos/ — histórico de fluxos de projeto

Cada subpasta aqui corresponde a um projeto iniciado via `/novo-projeto` (ou `harness-brainstorm`).

## Estrutura por projeto

```
.claude/projetos/
└── {slug-do-projeto}/          ← criado pelo harness-brainstorm
    ├── STATUS.md               ← fase atual + checklist + SI assessment
    ├── 00-ideia.md             ← ideia bruta + SI assessment + tipo de projeto
    ├── 01-grill.md             ← Q&A da sessão /grill-me (harness-define salva)
    ├── 02-prd.md               ← cópia do PRD.md gerado pelo /to-prd
    ├── 03-harness.md           ← decisões do /harness-architect (o que foi gerado e por quê)
    ├── 04-tasks-index.md       ← sumário das tasks criadas + link para tasks/
    └── 05-retro.md             ← retrospectiva ao shippar (harness-ship cria)
```

## Fluxo de fases

```
0. 00-ideia.md       /novo-projeto → harness-brainstorm
1. 01-grill.md       /grill-me → harness-define
2. 02-prd.md         /to-prd → harness-design
3. 03-harness.md     /harness-architect → harness-design
4. 04-tasks-index.md /to-tasks
5. (build)           harness-build (tasks/{slug}/NN-*.md)
6. 05-retro.md       harness-ship → /scorecard
```

## STATUS.md — o dashboard por projeto

Sempre leia o STATUS.md para saber em que fase o projeto está:

```
cat .claude/projetos/{slug}/STATUS.md
```

Ou liste todos:

```bash
ls .claude/projetos/
```

## Como iniciar um novo projeto

```
/novo-projeto
```

ou ative o agente diretamente:

```
harness-brainstorm
```

## Como retomar um projeto em andamento

Leia o STATUS.md do projeto:

```
cat .claude/projetos/{slug}/STATUS.md
```

Veja a fase atual e retome o passo correspondente:

| Fase | Próximo passo |
|---|---|
| 0 — Ideia capturada | /grill-me |
| 1 — Grill concluído | harness-design → /to-prd |
| 2 — PRD gerado | /harness-architect |
| 3 — Harness montado | /to-tasks |
| 4 — Tasks criadas | harness-build |
| 5 — Implementação | harness-ship |
| CONCLUÍDO | — |
