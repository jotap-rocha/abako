# Data Lineage (Linhagem de Dados)

## O que é

Rastreamento da origem e transformação de cada dado ao longo das camadas do pipeline.
Responde: "de onde veio esse dado?" e "o que aconteceu com ele?".

## Colunas de lineage por camada

Adicionar estas colunas é OBRIGATÓRIO em cada escrita de camada.

### Raw
```python
raw_df = raw_df \
    .withColumn("_source_file", lit(source_path)) \
    .withColumn("_ingest_ts", current_timestamp())
```

| Coluna | Tipo | O que registra |
|---|---|---|
| `_source_file` | string | Path ou URL do arquivo/endpoint de origem |
| `_ingest_ts` | timestamp | Momento exato da ingestão no Raw |

### Bronze
```python
bronze_df = bronze_df \
    .withColumn("_ingested_at", current_timestamp()) \
    .withColumn("_source", lit(source_name)) \
    .withColumn("_source_system", lit(source_system)) \
    .withColumn("_run_id", lit(run_id)) \
    .withColumn("_batch_id", lit(batch_id))
```

| Coluna | Tipo | O que registra |
|---|---|---|
| `_ingested_at` | timestamp | Momento de escrita no Bronze |
| `_source` | string | Nome do sistema de origem (ex: "erp-orders", "api-v2") |
| `_source_system` | string | Sistema de negócio lógico (ex: "SAP-ECC", "Salesforce") — capturado no brainstorm SDD |
| `_run_id` | string | ID único da execução do pipeline (UUID) |
| `_batch_id` | string | ID do batch/micro-batch (para incremental) |

### Silver
```python
silver_df = silver_df \
    .withColumn("_processed_at", current_timestamp()) \
    .withColumn("_pipeline_version", lit(pipeline_version)) \
    .withColumn("_source_system", col("_source_system"))  # propagar da Bronze
```

| Coluna | Tipo | O que registra |
|---|---|---|
| `_processed_at` | timestamp | Momento de escrita no Silver |
| `_pipeline_version` | string | Versão do código do pipeline (ex: "1.2.3") |

### Gold
```python
gold_df = gold_df \
    .withColumn("_updated_at", current_timestamp())
```

| Coluna | Tipo | O que registra |
|---|---|---|
| `_updated_at` | timestamp | Momento da última atualização da agregação |

## Gerando run_id e batch_id

```python
import uuid
from datetime import datetime

def generate_run_id() -> str:
    return str(uuid.uuid4())

def generate_batch_id(source: str, dt: datetime | None = None) -> str:
    ts = (dt or datetime.utcnow()).strftime("%Y%m%d_%H%M%S")
    return f"{source}_{ts}"
```

## Unity Catalog — lineage automático

No Databricks com Unity Catalog, o lineage de tabela e coluna é capturado automaticamente
quando se usa `saveAsTable()` com tabelas gerenciadas pelo Unity Catalog.

```python
# Exemplo: pipeline grava orders_silver a partir de orders_bronze
# Unity Catalog registra automaticamente:
#   orders_bronze → (transformation: SilverTransformer) → orders_silver

# Para ver no UI: Unity Catalog → Data Explorer → orders_silver → Lineage
```

Para acessar via API:

```python
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()
lineage = w.lineage_tracking.get_table_lineage("prd_catalog.silver.orders")
```

## Rastreabilidade end-to-end

Com as colunas de lineage, é possível responder:

```sql
-- "Esse pedido order_id=123 veio de qual arquivo?"
SELECT order_id, _source_file, _ingest_ts, _run_id
FROM dev_catalog.bronze.orders
WHERE order_id = '123'

-- "Quais pedidos foram processados no run_id X?"
SELECT COUNT(*), _pipeline_version
FROM dev_catalog.silver.orders
WHERE _run_id = 'abc-123-...'
GROUP BY _pipeline_version
```
