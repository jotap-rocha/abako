---
description: Atalho docs para telemetria live do fluxo SDD (emit/render/http.server opcional).
argument-hint: "[--slug <slug>] [--serve]"
---

# /fluxo-live — painel live do fluxo SDD

Telemetria **fail-soft** do mapa SDD 0–4. Complementa STATUS.md / scorecard — **não** substitui.
Ortogonal a evidence-gate (aceite hard) e agent-policies (Bash deny).

## Como o usuário vê o visual

1. Abra no browser (file:// ou editor):  
   `.claude/projetos/{slug}/fluxo/live.html`
2. Opcional — servir a pasta e atualizar no browser:  
   `python -m http.server 8765 --directory .claude/projetos/{slug}/fluxo`  
   → `http://localhost:8765/live.html`
3. Agents SDD (`harness-brainstorm`, `harness-build`) **devem avisar** esse path 1× no enter da fase.

Dev Loop **não** tem este painel no MVP.

## Uso CLI

```bash
# Emitir metadados (auto-render default; use --no-render para opt-out)
python -m config.fluxo_events emit \
  --slug {slug} --event-type agent_enter --agent harness-build --phase 3

# Regenerar HTML
python -m config.fluxo_events render --slug {slug}

# Ship: truncar trail
python -m config.fluxo_events truncate --slug {slug} --keep 100
```

## Honesty §1.3

Emit omitível/forjável; HTML pode ficar stale; telemetria local ≠ fidelidade perfeita.
Sem Edit policies nenhum gate impede de fato.

Ver: `docs/cheatsheets/fluxo-events-cheatsheet.md` · ADR `docs/adr/005-kernel-fluxo-events.md`.
