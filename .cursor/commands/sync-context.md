---
description: Sincroniza os arquivos de contexto (CLAUDE.md, AGENTS.md, CONTEXT.md, HANDOFF.md) com o código real. Obrigatório no fechamento de todo fluxo.
---

# /sync-context — fechar o ciclo de contexto

Detecte o drift entre o que os arquivos de contexto declaram e o que o código realmente é, e
corrija **só o que está implementado**. Contexto desatualizado é dívida que o próximo agente paga.

```bash
python3 .claude/skills/sync-context/scripts/check_context_drift.py --warn
```

Depois siga o processo da skill `.claude/skills/sync-context/SKILL.md`:

1. **Relatório primeiro** — mostre o drift (desatualizado / ausente / correto) e **aguarde
   confirmação** antes de editar qualquer arquivo.
2. **Aplique só o confirmado** — edite a seção específica, cite a evidência (`arquivo:linha`).
   Nunca documente funcionalidade planejada que não existe no código.
3. **Regenere o espelho** se o `CLAUDE.md` mudou:

```bash
python3 .claude/skills/sync-context/scripts/sync_agents_from_claude.py --apply
```

Este é o critério 7 da DoD (`rules/definicao-de-pronto.md`): o `harness-ship` e o step SYNC do
Dev Loop rodam isso automaticamente no fechamento. Rode explicitamente ao **abrir** sessão num
repo que ficou parado, ou quando o hook de `Stop` avisar que há drift.
