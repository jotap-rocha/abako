---
domain: cloud-platforms
topic: quick-reference
---

# Cloud Data Platforms — Quick Reference

### Unidade de compute e billing

| Plataforma | Unidade de compute | Granularidade | Storage cobrado à parte |
|---|---|---|---|
| Snowflake | Virtual warehouse (crédito/hora, T-shirt size) | Por segundo (min 60s) | Sim |
| Databricks | DBU + infra cloud (EC2/VM/GCE) | Por segundo (cluster) | Sim (é storage nativo do cloud, ex: S3/ADLS) |
| BigQuery | Slot (reservado) ou $/TB escaneado (on-demand) | Por query (on-demand) ou slot-hora | Sim |

### Arquitetura em 1 linha

| Plataforma | Arquitetura |
|---|---|
| Snowflake | Multi-cluster shared data: storage + compute + cloud services desacoplados |
| Databricks | Lakehouse sobre Delta Lake: formato aberto, data plane na conta do cliente |
| BigQuery | Serverless, motor Dremel, sem cluster visível ao usuário |

### Fit rápido por workload dominante

| Workload dominante | Plataforma que tende a se encaixar melhor |
|---|---|
| SQL analytics + BI, múltiplos times concorrentes | Snowflake |
| ML + engenharia de dados no mesmo pipeline | Databricks |
| GCP-nativo, zero-ops, analytics ad-hoc irregular | BigQuery |
| Data sharing entre organizações | Snowflake |
| Streaming em tempo real integrado a batch | Databricks |
| Portabilidade de dados / evitar lock-in de formato | Databricks (Delta Lake é aberto) |

### Checklist rápido de otimização de custo (as 3 plataformas)

1. Auto-suspend/autotermination configurado em todo compute interativo.
2. Compute de produção (batch/jobs) separado de compute exploratório (interativo).
3. Right-sizing medido com dado real de uso, nunca "chute para o pior caso".
4. Toda tabela grande tem estratégia de partição/clustering documentada.
5. Revisão mensal das queries de maior custo.

### Decision tree: escolher plataforma

```
Requisito dominante do workload?
    ├── SQL analytics + BI, isolamento entre times ────► Snowflake
    ├── ML + Engenharia de dados unificados ────────────► Databricks
    ├── GCP-nativo, zero-ops, workload irregular ───────► BigQuery
    └── Misto? ──► considerar combinação por camada (ver
                   patterns/platform-decision-checklist.md)
```

Ver [concepts/pricing-models.md](concepts/pricing-models.md),
[concepts/platform-architectures.md](concepts/platform-architectures.md) e
[concepts/workload-fit.md](concepts/workload-fit.md) para detalhe e trade-offs completos.
Ver [patterns/platform-decision-checklist.md](patterns/platform-decision-checklist.md) para o
processo completo de decisão (matriz de pontuação + PoC + ADR).
