---
topic: open-table-formats
confidence: null
mcp_validated: null
---

# Open Table Formats: Iceberg vs Delta Lake vs Hudi

## O que é um open table format

Camada de metadados sobre arquivos Parquet/ORC/Avro que dá a uma tabela em object storage (S3,
ADLS, GCS, HDFS) propriedades de banco relacional: transações ACID, schema enforcement/evolução,
time travel, particionamento independente do layout físico. Sem essa camada, um "diretório de
Parquet" é só arquivos — sem atomicidade, sem histórico, sem proteção contra leitura durante
escrita concorrente.

Os três formatos resolvem o mesmo problema (transformar arquivos em tabela transacional) com
modelos de metadados diferentes. Nenhum é universalmente "melhor" — a escolha depende do motor de
consumo dominante, do padrão de escrita (batch vs streaming/upsert-heavy) e do catálogo já em uso.

## Comparação

| Dimensão | Apache Iceberg | Delta Lake | Apache Hudi |
|---|---|---|---|
| Origem / governança | Netflix → Apache (neutro) | Databricks → Linux Foundation | Uber → Apache (neutro) |
| Metadados | Snapshots + manifest lists + manifest files (árvore) | Transaction log JSON (`_delta_log/*.json` + checkpoints Parquet) | Timeline (`.hoodie/`) + índice |
| Partition evolution | Nativa — muda spec sem reescrever dados antigos | Limitada (liquid clustering substitui partição fixa) | Limitada |
| Schema evolution | Field IDs únicos — rename/reorder/widen sem reescrita | Column mapping (ID/name mode) — suporta a maioria dos casos | Suporta, com mais restrições em nested types |
| Update/Delete (row-level) | Copy-on-write ou merge-on-read (delete files) | Copy-on-write ou deletion vectors (merge-on-read) | Merge-on-read é o caso de uso original (upsert-heavy) |
| Catálogo | Agnóstico — REST catalog, Hive Metastore, Glue, Nessie | Hive Metastore, Unity Catalog, Glue | Hive Metastore, Glue, AWS Glue |
| Motores com suporte nativo maduro | Spark, Trino, Flink, Snowflake, BigQuery, Databricks | Spark, Databricks (nativo), Trino/Presto (leitura), Flink | Spark, Flink, Presto/Trino (parcial) |
| Melhor encaixe | Multi-engine, catálogo aberto, partition evolution | Ecossistema Databricks/Spark, simplicidade operacional | Upserts/CDC de alta frequência, streaming incremental |

## Ponto de convergência (2025-2026)

Os três formatos convergem em interoperabilidade: Delta Lake expõe **UniForm** (gera metadados
Iceberg a partir de uma tabela Delta), e existem conectores para ler Hudi como Iceberg e
vice-versa via camadas de tradução. Na prática, a decisão "qual formato" importa menos hoje do que
"qual catálogo" — ver `concepts/metadata-catalogs.md`.

## Gotchas

- **Merge-on-read não é grátis**: delete files/deletion vectors aceleram escrita mas degradam leitura
  até compaction rodar — ver `patterns/compaction-small-files.md`.
- **Não misture engines sem catálogo compartilhado**: dois motores escrevendo na mesma tabela sem
  coordenar via catálogo (REST catalog, Hive Metastore) corrompe o estado transacional.
- **Time travel não é backup**: depende de `expire_snapshots`/`VACUUM` não terem rodado ainda —
  ver `concepts/time-travel-versioning.md` e `patterns/retention-vacuum.md`.
