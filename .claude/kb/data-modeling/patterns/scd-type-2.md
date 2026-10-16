# Implementação de SCD Type 2

Ver `concepts/scd-types.md` para o panorama dos 7 tipos. Este pattern cobre a implementação
completa do Type 2 — o caso mais comum.

## Schema da dimensão

```sql
CREATE TABLE dim_customer (
    customer_sk     BIGINT PRIMARY KEY,   -- surrogate key, gerado a cada nova versão
    customer_id     STRING NOT NULL,      -- natural key, estável entre versões
    customer_name   STRING NOT NULL,
    city            STRING NOT NULL,
    segment         STRING NOT NULL,
    hash_diff       STRING NOT NULL,      -- hash dos atributos rastreados, detecta mudança
    effective_date  TIMESTAMP NOT NULL,
    end_date        TIMESTAMP,            -- NULL = versão vigente
    is_current      BOOLEAN NOT NULL
);
```

## Passo 1 — Calcular hash dos atributos rastreados

Só rastreie os atributos que precisam de histórico (não todos — evita explosão de linhas para
campos voláteis, ver Gotchas em `concepts/scd-types.md`).

```python
import hashlib

def compute_hash_diff(row: dict, tracked_cols: list[str]) -> str:
    concat = "|".join(str(row[c]) for c in tracked_cols)
    return hashlib.sha256(concat.encode()).hexdigest()

tracked = ["city", "segment"]  # não rastreamos customer_name (baixo valor analítico)
```

## Passo 2 — Merge (upsert com versionamento)

```sql
-- Databricks / Delta Lake MERGE
MERGE INTO dim_customer AS target
USING staging_customer AS source
ON target.customer_id = source.customer_id AND target.is_current = true

WHEN MATCHED AND target.hash_diff != source.hash_diff THEN
  UPDATE SET
    target.end_date   = source._load_ts,
    target.is_current = false

WHEN NOT MATCHED THEN
  INSERT (customer_sk, customer_id, customer_name, city, segment,
          hash_diff, effective_date, end_date, is_current)
  VALUES (uuid(), source.customer_id, source.customer_name, source.city, source.segment,
          source.hash_diff, source._load_ts, NULL, true);

-- Segunda passada: inserir a nova versão para quem foi "fechado" acima
INSERT INTO dim_customer
SELECT
    uuid()              AS customer_sk,
    source.customer_id, source.customer_name, source.city, source.segment,
    source.hash_diff, source._load_ts AS effective_date,
    NULL AS end_date, true AS is_current
FROM staging_customer source
JOIN dim_customer target
  ON target.customer_id = source.customer_id
WHERE target.hash_diff != source.hash_diff
  AND target.end_date = source._load_ts;  -- só as que acabaram de ser fechadas
```

## Passo 3 — PySpark equivalente (fora de SQL puro)

```python
from delta.tables import DeltaTable
from pyspark.sql.functions import col, current_timestamp, lit

dim_table = DeltaTable.forName(spark, "dim_customer")

staging = staging_df.withColumn("hash_diff", sha2(concat_ws("|", "city", "segment"), 256))

# 1. Fecha versões antigas que mudaram
dim_table.alias("t").merge(
    staging.alias("s"),
    "t.customer_id = s.customer_id AND t.is_current = true"
).whenMatchedUpdate(
    condition="t.hash_diff != s.hash_diff",
    set={"end_date": "s._load_ts", "is_current": "false"}
).execute()

# 2. Insere novas versões (novos clientes + clientes que mudaram)
new_versions = staging.join(
    dim_table.toDF().filter(col("is_current") == False),
    "customer_id"
).filter(col("t.end_date") == col("s._load_ts"))
new_versions.write.format("delta").mode("append").saveAsTable("dim_customer")
```

## Como a fact table referencia SCD Type 2

A fact table sempre usa o `customer_sk` **vigente no momento do evento**, não o mais recente.
Isso preserva a correção histórica: uma venda de 2024 aponta para a versão de cliente que era
válida em 2024, mesmo que o cliente tenha mudado de cidade depois.

```sql
SELECT f.*, c.customer_sk
FROM staging_fact f
JOIN dim_customer c
  ON f.customer_id = c.customer_id
 AND f.event_ts >= c.effective_date
 AND (f.event_ts < c.end_date OR c.end_date IS NULL)
```

## Gotchas

- Nunca faça `UPDATE` direto na versão vigente para "corrigir" um erro de digitação — isso
  reescreve histórico. Erros de digitação são Type 1 num atributo separado, não Type 2.
- `effective_date` do staging deve vir do timestamp do evento de origem (CDC/ingestão), não do
  `current_timestamp()` do pipeline — senão o histórico fica preso à cadência de execução do job.
- Sempre valide que não existam 2 linhas com `is_current = true` para a mesma `customer_id`
  (constraint de qualidade de dados, não do banco) — é o erro mais comum de merge malfeito.
