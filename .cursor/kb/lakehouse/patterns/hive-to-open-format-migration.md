---
topic: hive-to-open-format-migration
confidence: null
mcp_validated: null
---

# Migração de Tabela Hive Tradicional para Formato Aberto

## Duas estratégias

| Estratégia | O que faz | Custo | Quando usar |
|---|---|---|---|
| In-place (metadata-only) | Gera metadados do novo formato apontando para os arquivos Parquet/ORC já existentes, sem reescrever dados | Baixo (minutos, não move bytes) | Dados já em Parquet, schema compatível, sem necessidade de reparticionar |
| Full rewrite (CTAS/backfill) | `CREATE TABLE ... AS SELECT` para uma tabela nova no formato aberto | Alto (reescreve todo o volume) | Dados em formato incompatível (CSV, ORC legado com tipos problemáticos), reparticionamento necessário, ou quer aproveitar para limpar dívida técnica |

## In-place — Iceberg

```sql
-- Opção A: promove a tabela Hive existente para Iceberg (mesmo nome, mesmo local)
CALL catalog.system.migrate('db.orders_hive');

-- Opção B: registra os arquivos existentes numa tabela Iceberg NOVA, sem mexer na original
-- (permite validar em paralelo antes de trocar o nome de produção)
CALL catalog.system.snapshot('db.orders_hive', 'db.orders_iceberg_shadow');

-- Se dados novos chegaram depois do snapshot inicial, adicionar incrementalmente:
CALL catalog.system.add_files('db.orders_iceberg_shadow', 'db.orders_hive');
```

## In-place — Delta Lake

```sql
CONVERT TO DELTA parquet.`s3://bucket/path/orders` PARTITIONED BY (order_date DATE);
```

Só funciona se os arquivos de origem já são Parquet — ORC/Avro/CSV exigem full rewrite.

## Full rewrite (qualquer formato)

```sql
CREATE TABLE catalog.db.orders_iceberg
USING iceberg
PARTITIONED BY (day(order_date))
AS SELECT * FROM db.orders_hive_legacy;
```

Mais caro, mas é a oportunidade de corrigir tipos problemáticos, reparticionar do zero (ver
`patterns/partition-evolution.md`) e já nascer com hidden partitioning em vez de colunas de
partição físicas herdadas do Hive.

## Checklist de migração

1. **Inventariar schema real**: tipos declarados no Hive Metastore às vezes divergem do que está
   fisicamente nos arquivos (schema drift silencioso) — validar antes de migrar, não depois.
2. **Mapear partition scheme**: decidir se o particionamento Hive atual (colunas físicas) faz
   sentido como hidden partitioning no formato novo, ou se é a chance de corrigir.
3. **Migrar em shadow (tabela paralela) quando possível** — nunca substituir a tabela de produção
   in-place sem período de validação com leitura dupla (old vs new) comparando contagens/hashes.
4. **Atualizar todos os consumidores** (jobs, dashboards, notebooks) para o novo catálogo/tabela
   antes de descomissionar a tabela Hive — big-bang cutover sem inventário de consumidores é a
   causa mais comum de incidente pós-migração.
5. **Congelar escritas na tabela Hive de origem** durante o snapshot/migrate, ou usar `add_files`
   incremental para capturar o delta escrito durante a janela de validação.
6. **Rollback plan**: manter a tabela Hive original intacta (read-only) por um período definido
   após o cutover — não deletar a fonte até confirmar que o novo formato está estável em produção.

## Gotchas

- **`migrate`/`CONVERT TO DELTA` alteram a tabela original in-place** — sempre têm uma variante
  "shadow" (`snapshot` no Iceberg) para quem quer validar sem risco antes do cutover definitivo.
- **Tipos incompatíveis silenciosos**: `TIMESTAMP` sem timezone no Hive vs `TIMESTAMP` com
  timezone no formato novo é a fonte de bug mais comum pós-migração — validar explicitamente.
- **Estatísticas/metadados não migram sozinhos**: rodar `ANALYZE`/computar estatísticas na tabela
  nova após a migração, senão o otimizador de query decide mal os primeiros planos.
- **Migração é read-only na origem, não é sincronização contínua**: se a tabela Hive continuar
  recebendo escritas depois da migração, é preciso um plano explícito de captura incremental
  (`add_files` repetido, ou CDC) — não confundir migração pontual com replicação contínua.
