---
description: >-
  Orientação sobre table format e catálogo — Iceberg, Delta Lake, governança de lakehouse.
  Aciona lakehouse-architect. Use quando: "monta tabelas Iceberg com X", "Delta ou Iceberg?".
---

# /lakehouse — table format e catálogo

Aciona o agente `lakehouse-architect`.

## Uso

```
/lakehouse <descrição do caso>
```

## Exemplos

```
/lakehouse "configura tabelas Iceberg com partition evolution"
/lakehouse "devo usar Delta Lake ou Iceberg?"
```

## O que acontece

1. `lakehouse-architect` avalia ecossistema existente, requisitos de engine e necessidade de governança
2. Consulta `.claude/kb/lakehouse/` (JIT)
3. Entrega matriz de decisão ou DDL/config concreta
4. Escala para `data-platform-engineer` (provisionamento) ou `spark-engineer` (leitura/escrita) quando aplicável

## Gate DE (kernel)

Antes de fechar entrega em tree DE (marker ou auto-detect SDP/DLT):

- **Agent amarrado:** `lakehouse-architect` — ver seção `Conformidade DE (kernel)` do agent
- **Gate:** `/validar` e/ou `python -m config.canonical_data_check validate <path>`
- **Norma:** `data-engineering.yaml` (não inventar regra aqui; remediação via skill `de-conformidade` quando disponível)
- Agent amarrado: DE-A* + pacote D.

