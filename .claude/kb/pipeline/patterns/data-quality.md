# Data Quality — Validação e Testes

## Comparação de ferramentas

| Ferramenta | Quando usar | Vantagem |
|---|---|---|
| **DLT Expectations** | Databricks, pipeline declarativo | Nativo, sem setup, métricas automáticas |
| **Great Expectations** | Agnóstico de plataforma | Flexível, Data Docs, suporta qualquer fonte |
| **dbt tests** | Projetos com dbt | Integrado ao modelo, versionado |
| **PySpark nativo** | Controle total, sem dependência extra | Zero overhead, customizável |

## DLT Expectations (Databricks Lakeflow)

```python
import dlt
from pyspark.sql.functions import col

@dlt.table(name="orders_silver")
@dlt.expect_all_or_drop({
    "order_id_not_null": "order_id IS NOT NULL",
    "amount_positive": "amount > 0",
    "valid_status": "status IN ('pending', 'confirmed', 'shipped', 'delivered', 'cancelled')",
})
def orders_silver():
    return (
        dlt.read("orders_bronze")
        .dropDuplicates(["order_id"])
    )
```

Modos de expectativa:
- `@dlt.expect` → log apenas (sem quarantine automática)
- `@dlt.expect_or_drop` → remove registro que viola
- `@dlt.expect_or_fail` → falha o pipeline se qualquer registro viola
- `@dlt.expect_all_or_drop` → múltiplas regras, descarta se qualquer uma falha

## PySpark nativo (sem dependências extras)

```python
from dataclasses import dataclass
from typing import Callable

@dataclass
class QualityRule:
    name: str
    check: Callable
    severity: str  # "fail" | "quarantine" | "log"

def validate_dataframe(
    df: DataFrame,
    rules: list[QualityRule],
    config: PipelineConfig,
    run_id: str,
) -> DataFrame:
    valid_df = df
    for rule in rules:
        failed = df.filter(~rule.check(df))
        count = failed.count()

        if count == 0:
            continue

        log.warning("quality_rule_failed",
            rule=rule.name,
            severity=rule.severity,
            count=count,
            run_id=run_id,
        )

        if rule.severity == "fail":
            raise DataQualityError(f"Quality rule failed: {rule.name} ({count} records)")
        elif rule.severity == "quarantine":
            send_to_quarantine(failed, reason=rule.name, run_id=run_id, config=config)
            valid_df = valid_df.filter(rule.check(valid_df))

    return valid_df


# Uso:
rules = [
    QualityRule("order_id_not_null", lambda df: df.order_id.isNotNull(), "fail"),
    QualityRule("amount_positive", lambda df: df.amount > 0, "quarantine"),
    QualityRule("no_future_dates", lambda df: df.created_at <= current_timestamp(), "log"),
]

silver_df = validate_dataframe(bronze_df, rules, config, run_id)
```

## Testes unitários de qualidade

```python
# tests/test_quality.py
import pytest
from pyspark.sql import SparkSession
from src.pipeline.orders.silver_transformer import OrdersSilverTransformer

@pytest.fixture(scope="session")
def spark():
    return SparkSession.builder.master("local[1]").appName("test").getOrCreate()

def test_silver_drops_duplicates(spark):
    data = [("1", 100.0), ("1", 100.0), ("2", 200.0)]
    df = spark.createDataFrame(data, ["order_id", "amount"])
    result = OrdersSilverTransformer().transform(df)
    assert result.count() == 2

def test_silver_filters_negative_amounts(spark):
    data = [("1", -10.0), ("2", 100.0), ("3", 0.0)]
    df = spark.createDataFrame(data, ["order_id", "amount"])
    result = OrdersSilverTransformer().transform(df)
    assert result.count() == 1
    assert result.first().order_id == "2"
```

## Regras de qualidade: bloqueante vs quarantine vs log

Configure por ambiente e por campo:

```yaml
# data-contracts/orders-v1.yaml — quality section
quality:
  rules:
    - field: order_id
      check: not_null
      severity: fail          # bloqueante: sem order_id = dados inúteis

    - field: amount
      check: "amount > 0"
      severity: quarantine    # quarantine: registra para análise, não bloqueia

    - field: created_at
      check: "created_at <= now()"
      severity: log           # apenas loga: datas futuras são suspeitas mas aceitáveis
```
