# Configuração Centralizada e Portabilidade

## O princípio

Zero hardcode. Trocar de ambiente = trocar 1 variável de ambiente.

```bash
PIPELINE_ENV=local  # dados locais, Spark local, sem notificações
PIPELINE_ENV=dev    # Databricks DEV workspace, notificações ligadas
PIPELINE_ENV=prd    # Databricks PRD workspace, thresholds mais restritivos
```

## Estrutura de arquivos

```
config/
├── pipeline_config.py          ← PipelineConfig dataclass (ver o arquivo)
└── environments/
    ├── local.yaml              ← desenvolvimento local
    ├── dev.yaml                ← Databricks DEV
    └── prd.yaml                ← Databricks PRD
```

## Como usar no pipeline

```python
from config.pipeline_config import PipelineConfig

config = PipelineConfig.from_env()  # lê PIPELINE_ENV

# Tabelas: substitui catalog/schema automaticamente
bronze_orders = config.bronze_table("orders")  # dev_catalog.bronze.orders
silver_orders = config.silver_table("orders")  # dev_catalog.silver.orders
quarantine   = config.quarantine_table()       # dev_catalog.bronze.quarantine

# Paths: funciona local e cloud
raw_path = config.raw_path("orders/2026-06-27/")
```

## Adicionando novo ambiente

1. Crie `config/environments/staging.yaml`
2. Copie o `dev.yaml` e ajuste os valores
3. Use: `PIPELINE_ENV=staging uv run python -m src.pipeline.orders.run`

Nenhuma linha de código muda.

## Multi-tenant / multi-cliente

Para pipelines que servem múltiplos clientes:

```yaml
# config/environments/cliente-a-prd.yaml
environment: prd
catalog: cliente_a_catalog
schema_bronze: bronze
```

```python
# Nenhuma lógica condicional no código:
config = PipelineConfig.from_env()  # PIPELINE_ENV=cliente-a-prd
bronze = config.bronze_table("orders")  # cliente_a_catalog.bronze.orders
```

## Portabilidade local → Databricks

```python
# Funciona idêntico nos dois ambientes:

config = PipelineConfig.from_env()

if config.is_local():
    spark = SparkSession.builder \
        .master(config.spark_master) \
        .appName(config.spark_app_name) \
        .getOrCreate()
else:
    # No Databricks, SparkSession já existe
    spark = SparkSession.getActiveSession()

# A partir daqui: mesmo código
df = spark.read.parquet(config.raw_path("orders/"))
df.write.saveAsTable(config.bronze_table("orders"))
```
