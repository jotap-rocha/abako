# Dev Loop

> **Agentic Development (nível intermediário)** — pergunta primeiro, executa com perfeição,
> recupera com graça.

Ver `DEV-LOOP.md` na raiz do repo para a introdução completa ao conceito. Este arquivo é o
overview rápido da pasta.

## Quick start

```bash
# Opção 1 — deixar o prompt-crafter guiar via perguntas (recomendado)
/dev "quero criar um parser de data"

# Opção 2 — executar um PROMPT já existente
/dev tasks/PROMPT_DATE_PARSER.md

# Opção 3 — criar o PROMPT manualmente
cp .claude/dev/templates/PROMPT_TEMPLATE.md .claude/dev/tasks/PROMPT_MINHA_TASK.md
/dev tasks/PROMPT_MINHA_TASK.md
```

## Estrutura da pasta

```
.claude/dev/
├── readme.md                        ← este arquivo
├── _index.md                        ← documentação técnica completa
├── tasks/                           ← seus PROMPT_*.md (trabalho ativo)
├── progress/                        ← memory bridge (auto-gerenciado)
├── logs/                            ← logs de execução (auto-gerados)
├── templates/
│   ├── PROMPT_TEMPLATE.md           ← template em branco
│   ├── PROGRESS_TEMPLATE.md
│   ├── PROMPT_EXAMPLE_FEATURE.md    ← exemplo: utilitário Python
│   └── PROMPT_EXAMPLE_KB.md         ← exemplo: domínio de KB
└── examples/                        ← exemplos reais acumulados neste repo
```

## Os dois agentes

| Agente | Quando | O que faz |
|---|---|---|
| `prompt-crafter` | Você descreve o que quer em linguagem natural | Pergunta, explora o código, gera o `PROMPT.md` |
| `dev-loop-executor` | Você já tem um `PROMPT.md` pronto | Executa as tasks com verificação, atualiza progresso, grava log |

## Ver também

- `DEV-LOOP.md` (raiz) — conceito, quando usar Dev Loop vs `/novo-projeto`
- `.claude/dev/_index.md` — documentação técnica completa (todas as opções, formatos de arquivo)
