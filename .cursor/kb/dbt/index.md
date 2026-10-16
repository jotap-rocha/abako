---
domain: dbt
description: dbt — model materializations, incremental strategies, testes, dbt Mesh, Fusion Engine
mcp_validated: "2026-07-26"
confidence: 0.95
---

# KB: dbt

Base de conhecimento de dbt (Core clássico + Fusion Engine) para transformação de dados
em SQL versionado, testado e modular. Princípio central: **model = select declarativo +
config de materialização** — orquestração externa, lógica de negócio em SQL/Jinja.

## Conformidade DE (ponte)

Fonte: `data-engineering.yaml` — este KB **não** duplica severidade nem texto normativo.

| Âncora | Relação |
|---|---|
| `DE-A*` | Universal |
| pacote **D** | se a tree for cloud/multi |

## Conceitos

| Arquivo | Tópico |
|---|---|
| [model-materializations.md](concepts/model-materializations.md) | view / table / incremental / ephemeral — quando usar cada uma |
| [incremental-strategies.md](concepts/incremental-strategies.md) | append / merge / delete+insert / microbatch |
| [testing-framework.md](concepts/testing-framework.md) | generic tests, singular tests, unit tests, severity |
| [dbt-mesh.md](concepts/dbt-mesh.md) | multi-projeto: cross-project ref, groups, access, contracts |
| [fusion-engine.md](concepts/fusion-engine.md) | motor Rust do dbt Core v2 — static analysis, v2 parser |

## Padrões

| Arquivo | Tópico |
|---|---|
| [incremental-merge-model.md](patterns/incremental-merge-model.md) | Receita de incremental model com `merge` — passo a passo + checklist |
| [snapshot-scd2.md](patterns/snapshot-scd2.md) | Snapshot para histórico de dimensão (SCD Type 2) |
| [custom-generic-test.md](patterns/custom-generic-test.md) | Testes genéricos reutilizáveis (primary_key, regex, faixa de valores) |
| [macro-patterns.md](patterns/macro-patterns.md) | Macro utilitária, dispatch por adapter, `statement()` block |
| [semantic-layer-metrics.md](patterns/semantic-layer-metrics.md) | Semantic Layer / MetricFlow — metrics reutilizáveis entre BI tools |

## Quick Reference

Ver [quick-reference.md](quick-reference.md) — layout de projeto canônico, invariantes
(DBT-01…DBT-06), decision tree materialization. Ler só se a tarefa exigir esse nível de
detalhe operacional.
