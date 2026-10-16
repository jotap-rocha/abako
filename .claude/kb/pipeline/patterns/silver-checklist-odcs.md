# Silver Checklist ODCS — camada Silver prescritiva

## Âncora normativa

- **Gate mecânico:** `DE-B003` exige contrato versionado (`data-engineering.yaml`).
- **Este pattern:** guia **implementação Silver** — dedup, limpeza semântica, validação.
- **Bronze:** tipagem explícita (`.cast()` / contrato) — ver [medallion.md](../concepts/medallion.md).
- Severidade DE (`blocker`) só no YAML; defaults operacionais abaixo são **prescritivos**.

## Proibido no Silver

Nunca faça na camada Silver (use Bronze ou Gold conforme o caso):

1. **Cast / inferSchema / inferência de tipo** — tipagem é Bronze; Silver só valida tipos já definidos.
2. **Ingestão Raw** — cópia da fonte sem transformação é Raw/Bronze.
3. **Agregações de negócio** — SUM, GROUP BY analítico, joins de domínio → Gold.
4. **`SELECT *`** — colunas explícitas (`DE-B002` no perfil spark-yarn).
5. **Filtrar “ruins” sem trilha** — violações vão para quarantine ou fail, nunca descarte silencioso.

## Severidade padrão

| Tipo de violação | Default | Ação |
|---|---|---|
| Uniqueness / dedup final falhou | **fail** | Interrompe job |
| Completeness batch abaixo do SLA | **fail** | Interrompe job |
| Freshness batch violada | **fail** | Interrompe job |
| Required null / blank | **quarantine** | Linha → quarantine |
| Enum / min / max inválido | **quarantine** | Linha → quarantine |
| Breaking change vs contrato | **quarantine** + notify | Política `versioning` |
| Normalização cosmética (trim, round) | **log** | Métrica estruturada |
| Lineage / metadados contrato | **log** | Colunas de auditoria |

Domínio pode sobrescrever no contrato ODCS com justificativa documentada.

## Template genérico (10 core + 5 opcionais)

Preencha a partir de `data-contracts/{entity}-vN.yaml`. Use `N/A` quando não aplicável.

| regra_id | categoria | mapeamento ODCS | severidade |
|---|---|---|---|
| SLV-CORE-001 | dedup | `quality.uniqueness.fields` | fail |
| SLV-CORE-002 | dedup | `quality.uniqueness.threshold` | fail |
| SLV-CORE-003 | limpeza | `schema.fields[*].required` (trim/null) | quarantine |
| SLV-CORE-004 | validação | `schema.fields[*].enum` | quarantine |
| SLV-CORE-005 | validação | `schema.fields[*].min` / `max` | quarantine |
| SLV-CORE-006 | validação | `quality.completeness` (batch) | fail |
| SLV-CORE-007 | validação | `quality.validity.*` | quarantine |
| SLV-CORE-008 | lineage | medallion `_processed_at`, `_pipeline_version`, `_run_id` | log |
| SLV-CORE-009 | lineage | contrato `_contract_id`, `_contract_version` | log |
| SLV-CORE-010 | sla | `versioning.breaking_change_policy` | quarantine |
| SLV-OPT-001 | dedup | CDC late-arriving (se `ingestion_mode: cdc`) | fail |
| SLV-OPT-002 | sla | `sla.freshness` | fail |
| SLV-OPT-003 | validação | anti-futuro em timestamps | quarantine |
| SLV-OPT-004 | validação | `relationships` / FK lógica | quarantine |
| SLV-OPT-005 | sla | volume esperado (`sla` / volume) | log |

### ingestion_mode (template contrato)

```yaml
# Campo opcional no contrato ODCS — guia dedup Silver
ingestion_mode: batch   # batch | cdc
```

| Modo | Dedup Silver |
|---|---|
| `batch` | `dropDuplicates([natural_key])` antes do write |
| `cdc` | `row_number()` + `MERGE` por chave natural + `created_at` |

## Instância orders (`orders-contract-v1`)

Contrato de referência: [data-contracts.md](../concepts/data-contracts.md) (`orders-v1.yaml`).

### SLV-ORD-001 — dedup por chave natural

- **ODCS:** `quality.uniqueness.fields: [order_id]`
- **Severidade:** fail

**PySpark:**

```python
silver_df = bronze_df.dropDuplicates(["order_id"])
```

**DLT:**

```python
@dlt.table(name="orders_silver")
def orders_silver():
    return dlt.read("orders_bronze").dropDuplicates(["order_id"])
```

### SLV-ORD-002 — threshold uniqueness 100%

- **ODCS:** `quality.uniqueness.threshold: 100%`
- **Severidade:** fail

**PySpark:**

```python
assert df.select("order_id").distinct().count() == df.count()
```

**DLT:**

```python
@dlt.expect_or_fail("unique_order_id", "count(*) = count(distinct order_id)")
```

### SLV-ORD-003 — order_id required + trim

- **ODCS:** `schema.fields[order_id].required`
- **Severidade:** quarantine

**PySpark:**

```python
from pyspark.sql.functions import col, length, trim

valid = df.filter(col("order_id").isNotNull() & (length(trim(col("order_id"))) > 0))
invalid = df.exceptAll(valid)  # → send_to_quarantine(invalid, "order_id_required", run_id, config)
```

**DLT:**

```python
@dlt.expect_or_drop("order_id_not_null", "order_id IS NOT NULL AND length(trim(order_id)) > 0")
```

### SLV-ORD-004 — customer_id required

- **ODCS:** `schema.fields[customer_id].required`
- **Severidade:** quarantine

**PySpark:** mesmo padrão SLV-ORD-003 para `customer_id`.

**DLT:**

```python
@dlt.expect_or_drop("customer_id_not_null", "customer_id IS NOT NULL")
```

### SLV-ORD-005 — round decimal (não re-tipar)

- **ODCS:** `schema.fields[amount].type: decimal(10,2)`
- **Severidade:** log

**PySpark:**

```python
from pyspark.sql.functions import col, round

# amount já tipado como decimal(10,2) no Bronze — só arredondar
df = df.withColumn("amount", round(col("amount"), 2))
```

**DLT:** expectation de formato; cast primário permanece no Bronze.

### SLV-ORD-006 — amount min + validity

- **ODCS:** `amount.min` + `quality.validity.amount_positive`
- **Severidade:** quarantine

**PySpark:**

```python
violations = df.filter(col("amount") < 0.01)  # → quarantine
silver_df = df.filter(col("amount") >= 0.01)
```

**DLT:**

```python
@dlt.expect_or_drop("amount_min", "amount >= 0.01")
```

### SLV-ORD-007 — status enum

- **ODCS:** `schema.fields[status].enum`
- **Severidade:** quarantine

**PySpark:**

```python
allowed = ("pending", "confirmed", "shipped", "delivered", "cancelled")
silver_df = df.filter(col("status").isin(allowed))
```

**DLT:**

```python
@dlt.expect_or_drop(
    "valid_status",
    "status IN ('pending','confirmed','shipped','delivered','cancelled')",
)
```

### SLV-ORD-008 — created_at required (+ anti-futuro opcional)

- **ODCS:** `schema.fields[created_at].required`
- **Severidade:** quarantine

**PySpark:**

```python
from pyspark.sql.functions import col, current_timestamp

silver_df = df.filter(
    col("created_at").isNotNull() & (col("created_at") <= current_timestamp())
)
```

**DLT:**

```python
@dlt.expect_or_drop("created_at_not_null", "created_at IS NOT NULL")
```

### SLV-ORD-009 — completeness batch

- **ODCS:** `quality.completeness: > 99%`
- **Severidade:** fail (batch); linhas → quarantine (SLV-ORD-003/004)

**PySpark:** métrica pré-write sobre campos required; abaixo de 99% → `raise` + `notify_owner`.

**DLT:** métricas DLT + fail job se SLA batch violada.

### SLV-ORD-010 — todos required

- **ODCS:** conjunto `schema.fields[*].required`
- **Severidade:** quarantine

**DLT:**

```python
@dlt.expect_all_or_drop({
    "order_id_not_null": "order_id IS NOT NULL",
    "customer_id_not_null": "customer_id IS NOT NULL",
    "created_at_not_null": "created_at IS NOT NULL",
})
```

### SLV-ORD-011 — lineage contrato

- **ODCS:** `id` + `version`
- **Severidade:** log

**PySpark:**

```python
df = df.withColumn("_contract_id", lit("orders-contract-v1")).withColumn(
    "_contract_version", lit("1.0.0")
)
```

### SLV-ORD-012 — lineage medallion

- **ODCS:** `producer.service`
- **Severidade:** log

**PySpark:**

```python
df = df.withColumn("_processed_at", current_timestamp()).withColumn(
    "_pipeline_version", lit("1.0.0")
).withColumn("_run_id", lit(run_id)).withColumn("_source_layer", lit("bronze"))
```

### SLV-ORD-013 — freshness SLA

- **ODCS:** `sla.freshness: "< 24 hours"`
- **Severidade:** fail

**PySpark:** alarme se `max(created_at)` do batch > 24h vs relógio de ingestão.

### SLV-ORD-014 — breaking change policy

- **ODCS:** `versioning.breaking_change_policy: quarantine_and_notify`
- **Severidade:** quarantine

Ver integração em [data-contracts.md](../concepts/data-contracts.md) (`ContractValidator`).

### SLV-ORD-015 — dedup CDC (opcional)

- **ODCS:** `ingestion_mode: cdc`
- **Severidade:** fail

**PySpark:**

```python
from pyspark.sql.window import Window
from pyspark.sql.functions import row_number

w = Window.partitionBy("order_id").orderBy(col("created_at").desc())
silver_df = df.withColumn("_rn", row_number().over(w)).filter(col("_rn") == 1).drop("_rn")
```

**DLT:** `MERGE` com condição `source.created_at > target.created_at`.

## Ver também

- [data-contracts.md](../concepts/data-contracts.md) — ODCS e integração Silver
- [medallion.md](../concepts/medallion.md) — fronteira de camadas
- [quarantine.md](../concepts/quarantine.md) — destino de inválidos
- [data-quality.md](data-quality.md) — expectations e ferramentas
- Skill `de-conformidade` — remediação `DE-B003`
