---
# Definição de Pronto (DoD) — carrega sempre (sem paths:)
---

# Definição de Pronto (DoD) + critérios de aceite

Regra **transversal**: define o que conta como "entregue e correto". É o contrato que torna
a execução do agente mensurável — sem ele, "está bom?" é inauditável. O `/scorecard` mede
a entrega contra esta definição.

## Toda task declara critérios de aceite

Critérios **testáveis**, escritos na task antes de implementar. Ex.: "POST /chat responde em
SSE", não "melhorar o chat". O que não é verificável não é critério de aceite.

## Uma task só está PRONTA quando (todos):

1. **Gate verde** — `/validar` (ruff + mypy + pytest) passa sem exceção. Não se comita vermelho.
2. **Evidence-gate verde** — `python -m config.evidence_gate collect|check` com manifesto em
   `evidencias/tasks/<id>.yaml`, logs e `evidencias_ref` na linha de `metrics/entregas.jsonl`.
   Hard e ortogonal ao `/validar` e ao `revisor-codigo` (soft). Waiver humano só se explícito
   no critério (`waiver.human: true`).
3. **Rules respeitadas** — nenhum invariante violado (SI, somente-leitura onde declarado, grafo
   determinístico, grounding com fonte, runtime puro).
4. **Revisor aprovou** — `revisor-codigo` com veredito `aprovado` (ou `aprovado com ressalvas`);
   **nenhum bloqueante** em aberto. O revisor **não** substitui o check mecânico do manifesto.
5. **Critérios de aceite atendidos** — cada um com evidência (teste que prova, ou demonstração
   com waiver).
6. **ADR registrado** se houve decisão contestável (`docs/adr/`).
7. **Delivery record gravado** em `metrics/entregas.jsonl` (1 linha JSON por task — schema em
   `metrics/README.md`, **incluindo `evidencias_ref`**). É o que alimenta o `/scorecard`.

## Um FLUXO só está FECHADO quando (além da DoD por task):

8. **Contexto sincronizado** — `/sync-context` rodado no fechamento (`harness-ship` ou
   `EXIT_COMPLETE` do Dev Loop), com o relatório de drift resolvido. `CLAUDE.md`, `CONTEXT.md`
   e `AGENTS.md` descrevem o código que existe agora, não o do início do fluxo.
   Contexto desatualizado é dívida que o próximo agente paga.
9. **Ship revalidou evidence-gate** — `check` das tasks do fluxo verde antes de fechar.

## Sinais lagging (medidos depois)

- **Change-failure:** task reaberta, bug aberto contra task já concluída, ou mudança pedida em
  revisão humana. Cada um conta contra a entrega; registre, não esconda.
- **Autonomia:** task concluída sem edição humana = entrega autônoma. A meta é essa taxa subir.

> Não persiga vaidade (linhas de código, nº de commits). O gate é alvo legítimo (testes reais);
> métricas de revisão humana não entram no que o agente otimiza.
