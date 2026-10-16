---
domain: pipeline
description: Conceitos e padrões de engenharia de dados — Medallion, contratos, lineage, schema evolution
mcp_validated: "2026-06-27"
confidence: 0.95
---

# KB: Pipeline de Dados

Base de conhecimento de engenharia de dados para projetos Medallion com boas práticas de
qualidade, lineagem, contratos e observabilidade.

## Conformidade DE (ponte)

Fonte: `data-engineering.yaml` — este KB **não** duplica severidade nem texto normativo.

| Âncora | Relação |
|---|---|
| `DE-A*` | Universal |
| pacotes **B** + **C** | Spark/YARN + Airflow quando a pipeline os usa |

## Conceitos

| Arquivo | Tópico |
|---|---|
| [medallion.md](concepts/medallion.md) | Arquitetura Raw→Bronze→Silver→Gold |
| [gold-analytic.md](concepts/gold-analytic.md) | Gold analítico (subset negócio, antes de Diamond) |
| [data-contracts.md](concepts/data-contracts.md) | ODCS-style YAML: schema + SLA + producer/consumer |
| [schema-evolution.md](concepts/schema-evolution.md) | mergeSchema vs quarantine vs fail |
| [data-lineage.md](concepts/data-lineage.md) | Colunas de lineage por camada, Unity Catalog lineage |
| [quarantine.md](concepts/quarantine.md) | Padrão de quarentena: tabela + notificação do owner |
| [observability.md](concepts/observability.md) | Structured logging, métricas por layer, alertas |

## Padrões

| Arquivo | Tópico |
|---|---|
| [solid-pipeline.md](patterns/solid-pipeline.md) | SOLID aplicado a pipelines de dados |
| [centralized-config.md](patterns/centralized-config.md) | PipelineConfig + environments/*.yaml |
| [notification.md](patterns/notification.md) | Webhook Slack/Teams/email para anomalias |
| [data-quality.md](patterns/data-quality.md) | DLT expectations vs Great Expectations vs dbt tests |
| [silver-checklist-odcs.md](patterns/silver-checklist-odcs.md) | Checklist Silver mapeado ao contrato ODCS |
| [medallion-sdd-gates.md](patterns/medallion-sdd-gates.md) | Gates SDD/Dev Loop antes de implementar pipeline |
| [genie-readiness.md](patterns/genie-readiness.md) | Checklist Genie/NL e governança semântica |

## Quick Reference

Ver [quick-reference.md](quick-reference.md) — colunas obrigatórias por camada, estratégias e
decision tree de schema evolution. Ler só se a tarefa exigir esse nível de detalhe.
