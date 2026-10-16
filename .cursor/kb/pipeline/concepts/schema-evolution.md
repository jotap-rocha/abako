# Schema Evolution

## O problema

Fontes de dados mudam. Colunas são adicionadas, removidas, renomeadas.
O pipeline precisa de uma estratégia explícita para cada tipo de mudança.

## 3 estratégias

### 1. mergeSchema (aceitar mudança não-breaking)

Quando: nova coluna NULLABLE foi adicionada à fonte (mudança aditiva).

```python
df.write \
  .mode("append") \
  .option("mergeSchema", "true") \
  .saveAsTable(config.bronze_table("orders"))
```

- Colunas existentes: mantidas
- Nova coluna: adicionada ao schema da tabela (nullable)
- Registros antigos: nova coluna fica `null`

**Cuidado**: só use se a nova coluna for nullable e o consumidor puder receber nulls.

### 2. quarantine + notify (mudança potencialmente breaking)

Quando: tipo mudou, coluna foi removida, nome foi alterado.

```python
def handle_schema_mismatch(
    df: DataFrame,
    expected_schema: StructType,
    config: PipelineConfig,
    run_id: str,
    contract: str,
) -> tuple[DataFrame, DataFrame]:
    """Separa registros com schema compatível dos problemáticos."""
    from pyspark.sql.functions import current_timestamp, lit

    try:
        valid_df = spark.createDataFrame(df.rdd, expected_schema)
        invalid_df = df.exceptAll(valid_df)
    except Exception as e:
        # Schema completamente incompatível — tudo vai para quarantine
        valid_df = spark.createDataFrame([], expected_schema)
        invalid_df = df.withColumn("_quarantine_reason", lit(str(e)))

    if invalid_df.count() > 0:
        quarantine_df = invalid_df \
            .withColumn("_quarantine_reason", lit("schema_mismatch")) \
            .withColumn("_quarantine_ts", current_timestamp()) \
            .withColumn("_run_id", lit(run_id)) \
            .withColumn("_contract", lit(contract))

        quarantine_df.write \
            .mode("append") \
            .saveAsTable(config.quarantine_table())

        notify_owner(config, reason="schema_mismatch", contract=contract, count=invalid_df.count())

    return valid_df, invalid_df
```

### 3. fail (violação de contrato declarado)

Quando: a mudança viola um contrato de dados existente e o consumidor depende do campo.

```python
def enforce_contract(df: DataFrame, contract: DataContract) -> DataFrame:
    violations = contract.validate(df)
    if violations:
        log.error("contract_violation",
            contract=contract.id,
            violations=violations,
            pipeline="orders_pipeline",
            layer="bronze",
        )
        raise ContractViolationError(
            f"Contract {contract.id} violated: {violations}. "
            "Open an ADR before accepting this schema change."
        )
    return df
```

## Decision tree

```
Schema detectado ≠ esperado?
    │
    ├── Mudança ADITIVA (nova coluna nullable)?
    │   └── strategy=merge  → mergeSchema
    │   └── strategy=quarantine → quarantine + notify
    │
    ├── Mudança POTENCIALMENTE BREAKING (tipo mudou, coluna sumiu)?
    │   └── quarantine + notify owner (sempre, independente de strategy)
    │
    └── Violação de CONTRATO DECLARADO?
        └── fail (exceção) + log + ADR obrigatório
```

## ADR obrigatório

Qualquer mudança de schema aceita intencionalmente deve ter um ADR em `docs/adr/`.

```
docs/adr/NNNN-schema-evolution-orders-v2.md
```

Contexto: por que a mudança ocorreu (fonte alterou o schema por negócio/técnico).
Decisão: aceitar com mergeSchema / requerer migração / manter v1 e criar v2.
Consequências: consumidores afetados, janela de migração.
