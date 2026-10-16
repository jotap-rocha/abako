# Estrutura-alvo do `.claude/` e arquivos-espelho

Ler no Passo 5 (Andaime o `.claude/`), depois de o Harness Plan estar confirmado. Gere só o
subconjunto que o plano pediu — não crie um subagente ou hook que o projeto não precisa.

```
.claude/
├── CLAUDE.md            # invariantes, stack, comandos, "nunca faça" — lido toda sessão
├── rules/               # regras path-scoped (uma por área: backend, frontend, etc.)
├── skills/              # operações repetíveis (pastas com SKILL.md)
├── agents/              # subagentes (contexto fresco, tarefas delegáveis)
├── commands/            # workflows (/feature, /poc, /run-evals)
├── settings.json        # hooks (gates de validação) + permissões (perímetro)
└── .mcp.json            # MCP servers para o agente inspecionar a infra (ex.: Postgres, Qdrant)
docs/adr/                # ADRs — a memória do "porquê" das decisões
HANDOFF.md               # template de handoff de sessão
AGENTS.md                # espelho portátil do CLAUDE.md — lido pelo Cursor, Windsurf, Codex
CONTEXT.md               # glossário de domínio — preenchido via /grill-with-docs
```

## `AGENTS.md` vs `CLAUDE.md`

O `CLAUDE.md` é Claude Code-específico (carrega rules, skills, MCP). O `AGENTS.md` é o
equivalente portátil para outros editores — contém stack, comandos, invariantes e "onde fica o
quê", mas sem referências a `.claude/` (que não existe nesses editores). Gere ambos sempre que o
projeto tiver `CLAUDE.md`.

## `CONTEXT.md`

Crie um esqueleto vazio com o template padrão e a instrução de preenchimento via
`/grill-with-docs`. Não invente termos do domínio — o conteúdo real vem do diálogo com o especialista.
