---
domain: data-quality
description: "Dimensões de qualidade de dados, data contracts ODCS e observabilidade de pipeline — Great Expectations, Soda, dbt tests, quarentena"
---

# KB: Data Quality

Base de conhecimento de qualidade de dados: dimensões formais de qualidade, contratos ODCS
(schema + SLA + producer/consumer) e observabilidade de pipeline (freshness, volume, schema
drift), com padrões de implementação em Great Expectations, Soda e dbt tests.

> Ver também: `pipeline/patterns/data-quality.md` — comparação de ferramentas focada em
> Databricks/DLT/PySpark nativo. Este domínio é o aprofundamento agnóstico de plataforma
> (ferramentas específicas, spec ODCS, dimensões formais).

## Conformidade DE (ponte)

Fonte: `data-engineering.yaml` — este KB **não** duplica severidade nem texto normativo.

| Âncora | Relação |
|---|---|
| `DE-A*` | Universal |
| `DE-D003` / `DE-D004` | quarentena DLT · schema rescue |

## Conceitos

| Arquivo | Tópico |
|---|---|
| [quality-dimensions.md](concepts/quality-dimensions.md) | Completude, unicidade, validade, consistência, atualidade |
| [data-contracts-odcs.md](concepts/data-contracts-odcs.md) | Estrutura ODCS: schema + SLA + producer/consumer + lifecycle |
| [pipeline-observability.md](concepts/pipeline-observability.md) | Data observability: freshness, volume, schema drift |

## Padrões

| Arquivo | Tópico |
|---|---|
| [great-expectations-suite.md](patterns/great-expectations-suite.md) | Suite de expectations, checkpoints, Data Docs |
| [soda-checks.md](patterns/soda-checks.md) | Checks declarativos SodaCL — YAML, freshness, anomaly detection |
| [dbt-tests.md](patterns/dbt-tests.md) | Schema tests, custom tests, source freshness, dbt-expectations |
| [quarantine-notification.md](patterns/quarantine-notification.md) | Roteamento para quarentena + notificação do owner, agnóstico de ferramenta |

## Quick Reference

Ver [quick-reference.md](quick-reference.md) — tabela de dimensões, decision tree de ferramenta
(GE vs Soda vs dbt tests) e severidade por dimensão. Ler só se a tarefa exigir esse nível de
detalhe.
