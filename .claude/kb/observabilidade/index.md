---
domain: observabilidade
description: Observabilidade para agentes LLM e pipelines — Langfuse traces, structured logging, métricas por camada
mcp_validated: "2026-06-27"
confidence: 0.90
---

# KB: Observabilidade

Base de conhecimento para observar, medir e depurar agentes LLM e pipelines de dados.
Princípio central: **trace cada run LLM + log estruturado em cada camada** — sem isso, debugging é cego.

## Conceitos

| Arquivo | Tópico |
|---|---|
| [langfuse-traces.md](concepts/langfuse-traces.md) | Traces, spans, scores e datasets no Langfuse |
| [structured-logging.md](concepts/structured-logging.md) | Logging estruturado com structlog — campos obrigatórios por camada |
| [metrics-by-layer.md](concepts/metrics-by-layer.md) | Métricas por camada: latência, custo, taxa de erro, qualidade |

## Padrões

| Arquivo | Tópico |
|---|---|
| [trace-llm-call.md](patterns/trace-llm-call.md) | Instrumentar chamadas LLM com Langfuse SDK |
| [alert-thresholds.md](patterns/alert-thresholds.md) | Thresholds de alerta por métrica — latência, custo, qualidade |

## Quick Reference

Ver [quick-reference.md](quick-reference.md) — stack de observabilidade, campos obrigatórios de
log, níveis por situação, invariantes (OBS-01…OBS-05). Ler só se a tarefa exigir esse nível de detalhe.
