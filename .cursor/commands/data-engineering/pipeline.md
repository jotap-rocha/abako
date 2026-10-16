---
description: >-
  Scaffolding de pipeline de dados (Airflow/Dagster) com padrões de boas práticas.
  Aciona pipeline-architect. Use quando: "cria uma DAG para X", "pipeline diário de Y".
---

# /pipeline — scaffolding de pipeline

Aciona o agente `pipeline-architect` para desenhar a orquestração.

## Uso

```
/pipeline <descrição ou path de spec>
```

## Exemplos

```
/pipeline "ETL diário de pedidos do Postgres pro data warehouse"
/pipeline "Kafka → staging → dbt → marts com refresh de hora em hora"
```

## O que acontece

1. `pipeline-architect` lê sua descrição, pergunta o que faltar (origem, destino, schedule, orquestrador)
2. Consulta `.claude/kb/airflow/` (JIT — só o arquivo relevante)
3. Gera a DAG com estrutura de tasks, dependências, retries e SLA
4. Escala para `dbt-specialist` se houver lógica de transformação SQL, ou `spark-engineer` se houver job Spark

## Gate DE (kernel)

Antes de fechar entrega em tree DE (marker ou auto-detect SDP/DLT):

- **Agent amarrado:** `pipeline-architect` — ver seção `Conformidade DE (kernel)` do agent
- **Gate:** `/validar` e/ou `python -m config.canonical_data_check validate <path>`
- **Norma:** `data-engineering.yaml` (não inventar regra aqui; remediação via skill `de-conformidade` quando disponível)
- Agent amarrado: DE-A* + B + C.

