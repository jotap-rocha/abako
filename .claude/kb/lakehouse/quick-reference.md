---
domain: lakehouse
topic: quick-reference
---

# Lakehouse — Quick Reference

### Formatos — resumo em uma linha

| Formato | Melhor encaixe |
|---|---|
| Iceberg | Multi-engine, catálogo aberto, partition evolution nativa |
| Delta Lake | Ecossistema Databricks/Spark, simplicidade operacional |
| Hudi | Upserts/CDC de alta frequência, streaming incremental |

### Catálogos — resumo em uma linha

| Catálogo | Melhor encaixe |
|---|---|
| Unity Catalog | Governança centralizada em ambiente Databricks |
| Iceberg REST Catalog | Multi-engine sem lock-in de vendor (Nessie, Polaris, Lakekeeper) |
| Glue Data Catalog | Stack 100% AWS já usando Athena/EMR/Redshift Spectrum |

### Comandos por operação

| Operação | Iceberg | Delta Lake |
|---|---|---|
| Time travel por versão | `VERSION AS OF <id>` | `VERSION AS OF <n>` |
| Time travel por timestamp | `TIMESTAMP AS OF '<ts>'` | `TIMESTAMP AS OF '<ts>'` |
| Rollback | `CALL system.rollback_to_snapshot(...)` | `RESTORE TABLE ... TO VERSION AS OF` |
| Evoluir partição | `ALTER TABLE ... ADD PARTITION FIELD` | `CLUSTER BY` (liquid clustering) |
| Compaction | `CALL system.rewrite_data_files(...)` | `OPTIMIZE ... [ZORDER BY (...)]` |
| Migrar de Hive (in-place) | `CALL system.migrate(...)` | `CONVERT TO DELTA` |
| Expirar snapshots | `CALL system.expire_snapshots(...)` | — (implícito no VACUUM) |
| Remover arquivos órfãos | `CALL system.remove_orphan_files(...)` | `VACUUM ... RETAIN <h> HOURS` |

### Decision tree: qual formato escolher

```
Workload é upsert/CDC de alta frequência (streaming)?
    └── SIM → considere Hudi (merge-on-read é o caso de uso original)
    └── NÃO
        ├── Ecossistema já é Databricks/Spark, quer simplicidade operacional?
        │   └── SIM → Delta Lake
        └── Múltiplos engines (Trino, Flink, Snowflake) precisam do mesmo catálogo,
            sem lock-in de vendor, ou precisa de partition evolution nativa?
            └── SIM → Iceberg
```

### Ordem segura de retenção (Iceberg)

```
1. rewrite_data_files (compaction)
2. expire_snapshots (older_than + retain_last)
3. remove_orphan_files (SEMPRE depois de expire_snapshots, nunca antes)
```

### Gotchas mais comuns (1 linha cada)

- Time travel só funciona enquanto o snapshot ainda não foi expirado — não é backup.
- `VACUUM`/`expire_snapshots` são destrutivos e irreversíveis — `DRY RUN` antes, sempre.
- Migração Hive→formato aberto altera a tabela original in-place — use variante "shadow" para
  validar antes do cutover.
- Partition evolution não retroage — dados antigos mantêm o spec com que foram escritos.

Detalhe completo: ver `concepts/` e `patterns/` correspondentes.
