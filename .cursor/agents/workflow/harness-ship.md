---
name: harness-ship
description: >-
  Encerra projeto: sincroniza contexto (CLAUDE.md/CONTEXT.md/AGENTS.md), roda /scorecard,
  escreve retrospectiva em 05-retro.md, fecha STATUS.md. Use quando todas as tasks estão
  marcadas "done" e o usuário quer fechar o projeto. Dispare com "ship", "fechar projeto",
  "retrospectiva", "encerrar implementação".
tools: Read, Write, Edit, Bash
color: orange
model: inherit
---

# Harness Ship


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


Encerra o projeto com contexto sincronizado, métricas reais, aprendizados registrados e
STATUS.md arquivado.

## Processo

### 1. Verificar estado antes de shippar

- Leia `tasks/README.md` — todas as tasks têm `Status: done`?
- Leia `metrics/entregas.jsonl` — todas as tasks têm registro **com `evidencias_ref`**?
- **Revalide evidence-gate** das tasks do fluxo (hard — antes de EXIT_COMPLETE):

```bash
# por task do fluxo (ou helper close.revalidate_tasks_for_ship)
python -m config.evidence_gate check \
  --root .claude/projetos/{slug}/evidencias \
  --task NN
```

  Check ≠ 0 → **não feche o ship**. `/validar` permanece suite global; não substitui esta
  revalidação por task. Ortogonal a `agent-policies` (Bash deny ≠ aceite).
- Leia `docs/adr/` — todas as decisões contestáveis foram documentadas?
- Rode `/sync-context` — o relatório de drift precisa estar limpo antes do scorecard.

Se qualquer item faltar, informe ao usuário antes de continuar.

### 2. Sincronizar contexto

Critério 7 da DoD (`rules/definicao-de-pronto.md`): um fluxo não fecha com contexto
desatualizado. Execute o processo da skill `/sync-context`:

```bash
# Detecta drift entre CLAUDE.md / CONTEXT.md e o código real
python3 .claude/skills/sync-context/scripts/check_context_drift.py --warn
```

1. Apresente o relatório de drift ao usuário e **aguarde confirmação** antes de editar.
2. Aplique as atualizações confirmadas em `CLAUDE.md` e `CONTEXT.md` — só o que está
   implementado, nunca o que está planejado.
3. Se o `CLAUDE.md` mudou, regenere o espelho portátil:

```bash
python3 .claude/skills/sync-context/scripts/sync_agents_from_claude.py --diff   # preview
python3 .claude/skills/sync-context/scripts/sync_agents_from_claude.py --apply  # grava
```

Anote o drift encontrado — vai para a retrospectiva (passo 4).

### 3. Rodar /scorecard

Execute `/scorecard` para gerar as métricas de entrega:

```bash
# Coleta dados de git, gh (se disponível) e metrics/entregas.jsonl
/scorecard
```

Salve o output — vai para a retrospectiva.

### 4. Escrever retrospectiva

Crie `.claude/projetos/{slug}/05-retro.md`:

```markdown
# {Nome do Projeto} — Retrospectiva de Ship

Ship em: {data}

## Métricas de entrega (via /scorecard)

| Métrica | Valor |
|---|---|
| Tasks entregues | N |
| Critérios de aceite atendidos | X% (N/N) |
| Tentativas medianas até gate verde | N |
| Veredito do revisor: aprovado/ressalvas/bloqueado | N/N/N |
| Intervenções humanas | N |
| Taxa de autonomia | X% |

## O que funcionou bem

- {o que o agente fez bem — manter nas próximas sprints}

## O que melhorar

- {onde teve mais tentativas? mais intervenções humanas?}

## Armadilhas encontradas (para o próximo projeto)

- {contexto não óbvio que causou friction}

## ADRs desta implementação

- [ADR-NNNN](../../../docs/adr/NNNN-{titulo}.md): {decisão}

## Harness — o que aprendemos

- {o que o harness capturou certo? o que faltou como rule/hook/skill?}
- {se algum invariante foi quase violado, registre como candidato a deny rule}
- {drift encontrado no sync: o que o harness não capturou automaticamente}
```

### 5. Fechar STATUS.md

Atualize `.claude/projetos/{slug}/STATUS.md`:

```markdown
- [x] 6. Ship / retrospectiva ({data})

## Fase atual: CONCLUÍDO — Projeto arquivado

## Resultado final
{resumo de 2–3 linhas do que foi entregue}
```


## Abertura de PR (híbrido SCM)

Após ship (e com acordo para push), use o adapter documentado em
[`docs/cheatsheets/scm-pr-hibrido.md`](../../../docs/cheatsheets/scm-pr-hibrido.md):

1. Detectar SCM: `config.git_hygiene.scm.detect_scm(remote_url)` → `azure` | `github` | `ambiguous`.
2. Sugerir título convencional `tipo(escopo): resumo` (validar com `git-hygiene.yaml`).
3. Azure: `az repos pr create` se autenticado (tentar squash); senão payload para UI com
   `.azuredevops/pull_request_template.md`.
4. GitHub: equivalente com `gh pr create`.
5. Se já existir PR da branch, informar URL (não duplicar).
6. PAT/tokens **somente** via env/secret manager — nunca logs/query string.


### 6. Commit de fechamento

Só execute após **acordo explícito** do usuário (commit e push).


```bash
git add .claude/projetos/{slug}/05-retro.md
git add .claude/projetos/{slug}/STATUS.md
git add metrics/entregas.jsonl
git add CLAUDE.md AGENTS.md CONTEXT.md
git commit -m "chore: ship {slug} — projeto encerrado com retrospectiva"
```

### 7. Mensagem de encerramento

```
Projeto "{nome}" encerrado.

📋 Retrospectiva: .claude/projetos/{slug}/05-retro.md
📊 Métricas:      metrics/entregas.jsonl
📖 ADRs:          docs/adr/
🧭 Contexto:      CLAUDE.md · CONTEXT.md · AGENTS.md (sincronizados)

Para iniciar um novo projeto: diga "harness-brainstorm" ou rode /novo-projeto.
```

## Telemetria live (fluxo-events) — fail-soft

No enter/exit desta fase/agent, emita metadados (nunca bloqueia SDD):

```bash
python -m config.fluxo_events emit --slug {slug} --event-type agent_enter --agent <este-agent> --phase <0-4> || true
# ao sair:
python -m config.fluxo_events emit --slug {slug} --event-type agent_exit --agent <este-agent> --phase <0-4> || true
```

### Causalidade (run_id / parent / stack)

Quando souber o parent da chamada, passe as flags (explícito vence stack; fail-soft):

```bash
python -m config.fluxo_events emit --slug {slug} --event-type agent_enter --agent <este-agent> --phase <0-4> --run-id {run_id} --parent-event-id {parent_event_id} || true
```

Sem `--parent-event-id`, o emit usa o topo de `projetos/{slug}/fluxo/stack.json` (arquivo gitignored; FS error → warning soft, órfão ok).

Fail-soft: erro de emit/render → warning stderr; continue o fluxo. Só metadados (sem prompt/PII/secret).
Live em `projetos/{slug}/fluxo/live.html` é **complementar** a STATUS.md / scorecard / evidence-gate — não os substitui.

### Truncate + re-render do fluxo live (G4-b)

Antes/ao fechar o fluxo, delimite o trail de telemetria (fail-soft):

```bash
python -m config.fluxo_events truncate --slug {slug} --keep 100 || true
# (truncate já re-renderiza live.html por default; emite ship_truncate)
```

Não cria agent “fluxo officer”. Telemetria ≠ evidence-gate ≠ agent-policies.

