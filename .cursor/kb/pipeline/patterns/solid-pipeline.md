# SOLID para Pipelines de Dados

## S — Single Responsibility

Cada classe tem UMA responsabilidade. Não misture camadas.

```python
class BronzeIngestor:
    """Só ingere: raw → bronze. Sem lógica de negócio."""
    def ingest(self, raw_path: str, config: PipelineConfig, run_id: str) -> DataFrame: ...

class SilverTransformer:
    """Só transforma: bronze → silver. Sem I/O."""
    def transform(self, df: DataFrame) -> DataFrame: ...

class GoldAggregator:
    """Só agrega: silver → gold. Sem validação."""
    def aggregate(self, df: DataFrame) -> DataFrame: ...
```

## O — Open/Closed

Extensível sem modificar. Use ABC + subclasses para novas transformações.

```python
from abc import ABC, abstractmethod
from pyspark.sql import DataFrame

class BaseTransform(ABC):
    @abstractmethod
    def transform(self, df: DataFrame) -> DataFrame:
        """Implementar para cada domínio."""
        ...

class OrdersSilverTransform(BaseTransform):
    def transform(self, df: DataFrame) -> DataFrame:
        return df.dropDuplicates(["order_id"]).filter(col("amount") > 0)

class CustomersSilverTransform(BaseTransform):
    def transform(self, df: DataFrame) -> DataFrame:
        return df.dropDuplicates(["customer_id"]).filter(col("email").isNotNull())

# Para adicionar novo domínio: crie nova subclasse, não modifique a base
```

## L — Liskov Substitution

Qualquer subclasse de `BaseTransform` é intercambiável.

```python
def run_silver_layer(transform: BaseTransform, df: DataFrame) -> DataFrame:
    """Aceita qualquer transform — não sabe qual é."""
    return transform.transform(df)

# Funciona com qualquer subclasse:
result = run_silver_layer(OrdersSilverTransform(), bronze_df)
result = run_silver_layer(CustomersSilverTransform(), bronze_df)
```

## I — Interface Segregation

Separe interfaces de leitura e escrita.

```python
from typing import Protocol

class Readable(Protocol):
    def read(self, path: str, config: PipelineConfig) -> DataFrame: ...

class Writable(Protocol):
    def write(self, df: DataFrame, table: str, config: PipelineConfig) -> None: ...

class DeltaReader:
    def read(self, path: str, config: PipelineConfig) -> DataFrame:
        return spark.read.format("delta").load(path)

class DeltaWriter:
    def write(self, df: DataFrame, table: str, config: PipelineConfig) -> None:
        df.write.mode("overwrite").saveAsTable(table)

class CsvReader:
    def read(self, path: str, config: PipelineConfig) -> DataFrame:
        return spark.read.csv(path, header=True, inferSchema=True)
```

## D — Dependency Inversion

Dependa de abstrações, não de implementações concretas.

```python
from dataclasses import dataclass

@dataclass
class Pipeline:
    """Orquestra sem saber quais implementações concretas são usadas."""
    reader: Readable
    transform: BaseTransform
    writer: Writable
    config: PipelineConfig

    def run(self, source_path: str, target_table: str, run_id: str) -> None:
        df = self.reader.read(source_path, self.config)
        transformed = self.transform.transform(df)
        self.writer.write(transformed, target_table, self.config)


# Composição (em tempo de criação, não de execução):
pipeline = Pipeline(
    reader=CsvReader(),
    transform=OrdersSilverTransform(),
    writer=DeltaWriter(),
    config=PipelineConfig.from_env(),
)
pipeline.run("s3://raw/orders/", config.silver_table("orders"), run_id)
```

## Exemplo completo — pipeline de pedidos

```python
# src/pipeline/orders/bronze_ingestor.py
class OrdersBronzeIngestor:
    def ingest(self, raw_path: str, config: PipelineConfig, run_id: str) -> DataFrame:
        df = spark.read.parquet(raw_path)
        return df \
            .select(
                col("id").cast("string").alias("order_id"),
                col("amount").cast("decimal(10,2)"),
                col("created_at").cast("timestamp"),
            ) \
            .withColumn("_ingested_at", current_timestamp()) \
            .withColumn("_source", lit("erp-orders")) \
            .withColumn("_run_id", lit(run_id)) \
            .withColumn("_batch_id", lit(generate_batch_id("orders")))

# src/pipeline/orders/silver_transformer.py
class OrdersSilverTransformer(BaseTransform):
    def transform(self, df: DataFrame) -> DataFrame:
        return df \
            .dropDuplicates(["order_id"]) \
            .filter(col("amount") > 0) \
            .withColumn("_processed_at", current_timestamp()) \
            .withColumn("_pipeline_version", lit("1.0.0"))

# src/pipeline/orders/run.py
def run_orders_pipeline(config: PipelineConfig, run_id: str) -> None:
    bronze = OrdersBronzeIngestor().ingest(config.raw_path("orders/"), config, run_id)
    bronze.write.mode("append").saveAsTable(config.bronze_table("orders"))

    pipeline = Pipeline(
        reader=DeltaReader(),
        transform=OrdersSilverTransformer(),
        writer=DeltaWriter(),
        config=config,
    )
    pipeline.run(config.bronze_table("orders"), config.silver_table("orders"), run_id)
```
