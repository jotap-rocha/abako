---
description: >-
  Autoria de contrato de dados (ODCS). Aciona data-contracts-engineer. Use quando: "cria um
  contrato entre o time de pedidos e analytics", "como evito breaking change nesse dataset?".
---

# /data-contract — contrato de dados

Aciona o agente `data-contracts-engineer`.

## Uso

```
/data-contract <descrição producer/consumer>
```

## Exemplos

```
/data-contract "contrato entre o time de pedidos e o time de analytics"
/data-contract "como formalizar SLA de freshness para o dataset de clientes?"
```

## O que acontece

1. `data-contracts-engineer` define schema, SLAs (freshness/completude/volume) e classificação PII
2. Consulta `.claude/kb/data-quality/concepts/data-contracts-odcs.md` (JIT)
3. Gera YAML ODCS-compliant com versionamento semântico
4. Escala para `data-quality-analyst` (implementação dos checks) ou `dbt-specialist` (testes dbt do contrato)

## Gate DE (kernel)

Antes de fechar entrega em tree DE (marker ou auto-detect SDP/DLT):

- **Agent amarrado:** `data-contracts-engineer` — ver seção `Conformidade DE (kernel)` do agent
- **Gate:** `/validar` e/ou `python -m config.canonical_data_check validate <path>`
- **Norma:** `data-engineering.yaml` (não inventar regra aqui; remediação via skill `de-conformidade` quando disponível)
- Agent amarrado já declara DE-A* (+ D se cloud).

