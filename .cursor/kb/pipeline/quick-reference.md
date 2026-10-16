---
domain: pipeline
topic: quick-reference
---

# Pipeline de Dados — Quick Reference

### Colunas obrigatórias por camada

| Camada | Colunas obrigatórias |
|---|---|
| Raw | `_source_file`, `_ingest_ts` |
| Bronze | `_ingested_at`, `_source`, `_source_system`, `_run_id`, `_batch_id` |
| Silver | `_processed_at`, `_pipeline_version`, `_source_system` |
| Gold | `_updated_at` |

### Estratégias de schema evolution

| Situação | Estratégia |
|---|---|
| Nova coluna opcional (não-breaking) | `mergeSchema` |
| Tipo mudou / coluna removida | `quarantine` + notificar owner |
| Violação de contrato de dados | `fail` |

### Decision tree: schema evolution

```
Schema detectado ≠ esperado?
    ├── Diferença é ADITIVA (nova coluna nullable)?
    │   └── strategy=merge? → mergeSchema → processa normalmente
    │   └── strategy=quarantine? → quarantine + notify
    ├── Diferença é POTENCIALMENTE BREAKING (tipo mudou, coluna sumiu)?
    │   └── quarantine + notify owner (sempre)
    └── Violação de contrato declarado?
        └── fail (lança exceção + log estruturado)
```
