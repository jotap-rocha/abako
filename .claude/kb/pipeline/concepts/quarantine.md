# Tabela de Quarantine

## O que é

Destino para registros que não passaram na validação de schema ou qualidade.
Preserva os dados originais + motivo da rejeição + metadados de rastreamento.
Permite análise posterior e reprocessamento quando o problema for corrigido.

## Estrutura da tabela de quarantine

```
{catalog}.bronze.quarantine
```

Colunas adicionadas automaticamente:

| Coluna | Tipo | Conteúdo |
|---|---|---|
| `_quarantine_reason` | string | Motivo da quarentena (ex: "schema_mismatch", "null_required_field") |
| `_quarantine_ts` | timestamp | Momento em que foi enviado para quarantine |
| `_run_id` | string | ID do run que detectou o problema |
| `_contract` | string | Nome do contrato violado (se aplicável) |
| `_original_schema` | string | Schema detectado (JSON string) |
| + todos os campos originais | * | Os dados brutos exatamente como vieram |

## Criando a quarantine table (DDL)

```sql
-- Databricks SQL / Unity Catalog
CREATE TABLE IF NOT EXISTS dev_catalog.bronze.quarantine (
    _quarantine_reason STRING NOT NULL,
    _quarantine_ts TIMESTAMP NOT NULL,
    _run_id STRING NOT NULL,
    _contract STRING,
    _original_schema STRING,
    -- Dados originais como JSON ou colunas individuais (depende do pipeline)
    _raw_data STRING
)
USING DELTA
PARTITIONED BY (date(_quarantine_ts))
TBLPROPERTIES (
    'delta.autoOptimize.optimizeWrite' = 'true',
    'delta.autoOptimize.autoCompact' = 'true'
);
```

## Padrão de escrita

```python
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.functions import current_timestamp, lit, to_json, struct

def send_to_quarantine(
    df: DataFrame,
    reason: str,
    run_id: str,
    config: PipelineConfig,
    contract: str = "",
) -> None:
    """Envia registros problemáticos para a quarantine table."""
    if df.isEmpty():
        return

    quarantine_df = df \
        .withColumn("_quarantine_reason", lit(reason)) \
        .withColumn("_quarantine_ts", current_timestamp()) \
        .withColumn("_run_id", lit(run_id)) \
        .withColumn("_contract", lit(contract)) \
        .withColumn("_raw_data", to_json(struct([df[c] for c in df.columns])))

    # Seleciona apenas as colunas de controle + _raw_data
    quarantine_cols = [c for c in quarantine_df.columns if c.startswith("_")]
    quarantine_df.select(quarantine_cols) \
        .write \
        .mode("append") \
        .saveAsTable(config.quarantine_table())

    log.warning("records_quarantined",
        pipeline="pipeline",
        reason=reason,
        count=df.count(),
        run_id=run_id,
        contract=contract,
    )
```

## Notificação do owner

```python
import httpx

def notify_owner(
    config: PipelineConfig,
    reason: str,
    contract: str,
    count: int,
    run_id: str,
) -> None:
    if not config.notifications_enabled:
        return

    message = {
        "text": (
            f":warning: *Pipeline Anomaly*\n"
            f"*Reason:* {reason}\n"
            f"*Contract:* {contract}\n"
            f"*Records quarantined:* {count}\n"
            f"*Run ID:* {run_id}\n"
            f"*Environment:* {config.environment}\n"
            f"Check: `{config.quarantine_table()}`"
        )
    }

    if config.slack_webhook_url:
        httpx.post(config.slack_webhook_url, json=message, timeout=5)

    if config.owner_email:
        # Integre com seu sistema de email aqui (SendGrid, SES, etc.)
        pass
```

## Reprocessamento da quarantine

Quando o problema é corrigido (ex: schema da fonte foi normalizado):

```python
# 1. Leia a quarantine
quarantine_df = spark.read.table(config.quarantine_table()) \
    .filter(col("_quarantine_reason") == "schema_mismatch") \
    .filter(col("_run_id") == "run-id-com-problema")

# 2. Extraia os dados originais
raw_df = quarantine_df.select(from_json(col("_raw_data"), original_schema).alias("data")) \
    .select("data.*")

# 3. Reprocesse normalmente
bronze_df = transform_to_bronze(raw_df, config, new_run_id)
bronze_df.write.mode("append").saveAsTable(config.bronze_table("orders"))

# 4. Marque como reprocessado na quarantine
# (não delete — adicione coluna _reprocessed_at e _reprocessed_run_id)
```
