---
description: >-
  Revisão de código focada em SQL — usa o revisor-codigo deste harness + sql-optimizer para
  análise de query plan e padrões de dialeto. Use quando: "revisa esse SQL", "essa query
  está lenta, revisa".
---

# /sql-review — revisão de código SQL

Aciona `revisor-codigo` (`.claude/agents/dev/`) para a revisão geral, com escalonamento para
`sql-optimizer` quando o achado for de performance/dialeto — **não** importa um agente de
review duplicado, reusa o que este harness já tem.

## Uso

```
/sql-review <path>
```

## Exemplos

```
/sql-review models/staging/
/sql-review backend/app/repositories/pedidos.py
```

## O que acontece

1. `revisor-codigo` revisa o diff/arquivo contra as regras do projeto (SI, correção, invariantes)
2. Se o achado for otimização de query (plano de execução, window function, tradução de dialeto), escala para `sql-optimizer` (`.claude/kb/sql-patterns/`, JIT)
3. Se o achado for teste/model dbt, escala para `dbt-specialist`

## Gate DE (kernel)

Antes de fechar entrega em tree DE (marker ou auto-detect SDP/DLT):

- **Agent amarrado:** `sql-optimizer` (revisão geral: `revisor-codigo`) — ver seção `Conformidade DE (kernel)` do agent
- **Gate:** `/validar` e/ou `python -m config.canonical_data_check validate <path>`
- **Norma:** `data-engineering.yaml` (não inventar regra aqui; remediação via skill `de-conformidade` quando disponível)
- Agent DE amarrado: DE-A* (+ D se cloud).

