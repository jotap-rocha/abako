---
domain: cloud-platforms
description: "Comparativo entre plataformas de dados em nuvem — Snowflake, Databricks, BigQuery: precificação, arquitetura, encaixe por workload, otimização de custo"
---

# KB: Cloud Data Platforms — Índice

Base de conhecimento **comparativa** (não prescritiva) entre Snowflake, Databricks e BigQuery.
O harness é stack-agnostic por princípio — este domínio existe para embasar decisão de trade-off,
não para recomendar uma única plataforma como "certa".

## Conformidade DE (ponte)

Fonte: `data-engineering.yaml` — este KB **não** duplica severidade nem texto normativo.

| Âncora | Relação |
|---|---|
| `DE-A*` | Universal |
| pacote **D** (`DE-D*`) | checks cloud / Databricks (sem live API) |

## Princípio central

> **Nenhuma plataforma vence em todos os cenários.** O encaixe depende do perfil de workload
> (SQL/BI vs ML/engenharia vs analytics ad-hoc), do skillset do time e do cloud provider já
> dominante na organização.

## Conceitos

| Arquivo | Tópico |
|---|---|
| [pricing-models.md](concepts/pricing-models.md) | Compute separado de storage: warehouse (Snowflake), DBU (Databricks), slots (BigQuery) |
| [platform-architectures.md](concepts/platform-architectures.md) | Multi-cluster shared data, Lakehouse/Delta Lake, serverless Dremel |
| [workload-fit.md](concepts/workload-fit.md) | Quando cada plataforma se encaixa melhor por perfil de carga |

## Padrões

| Arquivo | Tópico |
|---|---|
| [cost-optimization.md](patterns/cost-optimization.md) | Auto-suspend/autotermination, right-sizing, particionamento/clustering |
| [platform-decision-checklist.md](patterns/platform-decision-checklist.md) | Checklist + decision tree + matriz de pontuação para escolher plataforma |

## Agentes disponíveis

Nenhum ainda — domínio criado para embasar o agente `data-platform-engineer`
(`.claude/agents/data-engineering/`), a ser criado em evolução futura do harness.

## Quick Reference

Ver [quick-reference.md](quick-reference.md) — tabela comparativa rápida de precificação,
arquitetura e fit por workload. Ler só se a tarefa exigir esse nível de detalhe.

## Status de validação

Este domínio **ainda não foi validado via Context-7 MCP** — o conteúdo foi elaborado com
conhecimento geral e publicamente documentado das três plataformas, sem consulta a fonte externa
nesta sessão. `mcp_validated: null` e `confidence: null` em `_index.yaml` até a primeira
validação real ocorrer (Modo 2 — Auditar KB existente).
