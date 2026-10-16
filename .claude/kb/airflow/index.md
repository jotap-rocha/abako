---
domain: airflow
description: Apache Airflow 3.x — DAGs com TaskFlow API, scheduling orientado a assets, sensors, XComs, dynamic task mapping, pools/prioridade
mcp_validated: null
confidence: null
---

# KB: Apache Airflow

Base de conhecimento de padrões Airflow 3.x para orquestração de pipelines de dados.
Princípio central: **DAGs idempotentes e determinísticas** — reexecutar uma task com o mesmo
`logical_date`/input produz o mesmo resultado, sem efeitos colaterais duplicados.

## Conformidade DE (ponte)

Fonte: `data-engineering.yaml` — este KB **não** duplica severidade nem texto normativo.

| Âncora | Relação |
|---|---|
| `DE-A*` | Universal em qualquer tree DE |
| pacote **C** (`DE-C*`) | checks Airflow (condicional) |
| pacotes A+B | pipeline batch com Spark/YARN quando coexiste |

## Conceitos

| Arquivo | Tópico |
|---|---|
| [dag-anatomy.md](concepts/dag-anatomy.md) | Anatomia de uma DAG com TaskFlow API — `@dag`, `@task`, dependências implícitas |
| [asset-scheduling.md](concepts/asset-scheduling.md) | Scheduling orientado a assets/datasets — `schedule=[asset]`, `@asset`, `AssetAlias` |
| [sensors-vs-operators.md](concepts/sensors-vs-operators.md) | Sensor espera condição, operator executa ação — poke vs reschedule vs deferrable |
| [xcom-communication.md](concepts/xcom-communication.md) | Comunicação entre tasks via XCom — auto XCom do TaskFlow, limites, custom backends |

## Padrões

| Arquivo | Tópico |
|---|---|
| [idempotent-dag-retry.md](patterns/idempotent-dag-retry.md) | DAG idempotente com retry/backoff exponencial e particionamento por `logical_date` |
| [sensor-pattern.md](patterns/sensor-pattern.md) | Sensor deferrable para dependência externa (arquivo, API, outra DAG) sem ocupar worker |
| [dynamic-task-mapping.md](patterns/dynamic-task-mapping.md) | `expand()`/`partial()` para fan-out dinâmico baseado em dados de runtime |
| [pools-priority.md](patterns/pools-priority.md) | Pools e `priority_weight` para controlar concorrência em recursos compartilhados |

## Quick Reference

Ver [quick-reference.md](quick-reference.md) — layout canônico, invariantes (AF-01…AF-07),
decision tree operator vs sensor vs asset. Ler só se a tarefa exigir esse nível de detalhe
operacional.

## Nota de validação

Este domínio foi criado sem passar pelo Context-7 MCP (ferramenta indisponível nesta sessão) —
`mcp_validated`/`confidence` estão `null` até a primeira validação real. Auditar antes de usar
em produção crítica (ver Modo 2 do `kb-architect`).
