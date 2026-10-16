---
domain: data-quality
topic: quick-reference
---

# Data Quality — Quick Reference

### As 5 dimensões

| Dimensão | Pergunta | Exemplo de check |
|---|---|---|
| Completude | Campo obrigatório preenchido? | `missing_count(order_id) = 0` |
| Unicidade | Existe duplicata na chave de negócio? | `duplicate_count(order_id) = 0` |
| Validade | Valor respeita formato/enum/range? | `invalid_count(status)` |
| Consistência | Campos/tabelas relacionadas coerentes? | `relationships` (dbt) |
| Atualidade | Dado fresco dentro do SLA? | `freshness(_ingested_at) < 24h` |

Detalhe completo: `concepts/quality-dimensions.md`.

### Decision tree: qual ferramenta usar

```
Projeto já usa dbt para transformação?
    └── SIM → dbt tests (schema tests + dbt-expectations) — zero infra extra

Precisa de checks legíveis por não-engenheiros / monitoramento contínuo standalone?
    └── SIM → Soda (SodaCL declarativo + anomaly detection nativa)

Precisa de suite reutilizável entre pipelines + documentação viva (Data Docs)?
    └── SIM → Great Expectations

Projeto é 100% Databricks/DLT?
    └── SIM → ver pipeline/patterns/data-quality.md (DLT Expectations)
```

### Severidade por dimensão (default)

| Dimensão violada | Severidade | Ação |
|---|---|---|
| Completude em PK | `fail` | Aborta pipeline |
| Unicidade em PK | `quarantine` | Isola + notifica owner |
| Validade | `quarantine` | Isola + notifica owner |
| Consistência | `quarantine` | Isola + notifica owner |
| Atualidade | `log` + alerta | Sem linha para isolar — é sinal de pipeline |

Detalhe completo: `patterns/quarantine-notification.md`.

### ODCS — seções obrigatórias de um contrato

`producer` · `consumers` · `schema.logical` · `sla.freshness` · `quality` · `lifecycle`.
Sem `lifecycle.breaking_change_policy`, não existe processo de deprecation — trate como
gap bloqueante em revisão de contrato. Detalhe completo: `concepts/data-contracts-odcs.md`.

### Os 3 pilares de data observability

`freshness` (dado atualizado?) · `volume` (contagem dentro do baseline?) ·
`schema drift` (schema mudou sem aviso?). Detalhe completo: `concepts/pipeline-observability.md`.
