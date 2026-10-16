---
name: grill-me
description: Interview the user relentlessly about a plan or design until reaching shared understanding, resolving each branch of the decision tree. Use when user wants to stress-test a plan, get grilled on their design, or mentions "grill me".
---

Interview me relentlessly about every aspect of this plan until we reach a shared understanding. Walk down each branch of the design tree, resolving dependencies between decisions one-by-one. For each question, provide your recommended answer.

Ask the questions one at a time.

If a question can be answered by exploring the codebase, explore the codebase instead.

## Key vault / secrets cloud (quando o plano usa cofre)

Se o plano ou SI assessment indicar **key vault** / secrets cloud, inclua na árvore
(e confirme no `harness-define`):

1. Qual provedor? **OCI Vault** | **Azure Key Vault** | **ambos (multi)**
2. Default sugerido por stack — **sempre** peça confirmação humana:
   - Databricks / Azure host → sugerir **Azure**
   - Sinal OCI → sugerir **OCI**
   - Ambíguo → **sem default** (forçar escolha)
3. Não deixe a escolha só implícita no install ou em commands DE — o wiring da
   pergunta é **grill/define** apenas.

Playbook pós-escolha: skill `cloud-secrets` + KBs `oci-vault` / `azure-keyvault`.

## Telemetria live (fluxo-events) — fail-soft

No enter/exit desta fase/agent, emita metadados (nunca bloqueia SDD):

```bash
python -m config.fluxo_events emit --slug {slug} --event-type agent_enter --agent <este-agent> --phase <0-4> || true
# ao sair:
python -m config.fluxo_events emit --slug {slug} --event-type agent_exit --agent <este-agent> --phase <0-4> || true
```

Fail-soft: erro de emit/render → warning stderr; continue o fluxo. Só metadados (sem prompt/PII/secret).
Live em `projetos/{slug}/fluxo/live.html` é **complementar** a STATUS.md / scorecard / evidence-gate — não os substitui.

