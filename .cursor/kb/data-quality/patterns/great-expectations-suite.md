---
topic: great-expectations-suite
confidence: null
mcp_validated: null
---

# Suite de Expectations com Great Expectations

> Ver também: `pipeline/patterns/data-quality.md` — compara GE com DLT Expectations, dbt tests e
> PySpark nativo. Este arquivo aprofunda o uso do Great Expectations especificamente.

## Quando usar

Great Expectations quando o projeto precisa de: (1) validação agnóstica de plataforma
(funciona com Pandas, Spark, SQL, arquivos), (2) documentação viva gerada automaticamente
(Data Docs), (3) suíte de regras reutilizável entre pipelines diferentes.

## Conceitos-chave

| Termo | O que é |
|---|---|
| `Expectation` | Uma regra individual (ex.: `expect_column_values_to_not_be_null`) |
| `ExpectationSuite` | Conjunto nomeado de expectations para um dataset |
| `Data Context` | Configuração do projeto GE (datasources, stores, Data Docs) |
| `Checkpoint` | Execução de uma suite contra um batch de dados + ações pós-validação |
| `Data Docs` | HTML gerado automaticamente com o resultado de cada validação |

## Criando uma suite

```python
import great_expectations as gx

context = gx.get_context()

datasource = context.sources.add_pandas("orders_datasource")
asset = datasource.add_dataframe_asset(name="orders_silver")
batch_request = asset.build_batch_request(dataframe=orders_df)

suite = context.add_or_update_expectation_suite("orders_silver_suite")
validator = context.get_validator(
    batch_request=batch_request,
    expectation_suite_name="orders_silver_suite",
)

# Completude
validator.expect_column_values_to_not_be_null("order_id")
validator.expect_column_values_to_not_be_null("customer_id")

# Unicidade
validator.expect_column_values_to_be_unique("order_id")

# Validade
validator.expect_column_values_to_be_between("amount", min_value=0.01, max_value=1_000_000)
validator.expect_column_values_to_be_in_set(
    "status", ["pending", "confirmed", "shipped", "delivered", "cancelled"]
)

# Atualidade (proxy: idade máxima do registro mais antigo do batch)
validator.expect_column_max_to_be_between(
    "_ingested_at", min_value=None, max_value=None,  # comparar contra now() - SLA em runtime
)

validator.save_expectation_suite(discard_failed_expectations=False)
```

## Rodando via Checkpoint

```python
checkpoint = context.add_or_update_checkpoint(
    name="orders_silver_checkpoint",
    validations=[
        {
            "batch_request": batch_request,
            "expectation_suite_name": "orders_silver_suite",
        }
    ],
)

result = checkpoint.run()

if not result.success:
    failed = [r for r in result.list_validation_results() if not r["success"]]
    # Roteie para quarantine — ver patterns/quarantine-notification.md
    raise DataQualityError(f"{len(failed)} expectations falharam: {result}")
```

## Integração em pipeline Spark

```python
datasource = context.sources.add_spark("orders_spark_datasource")
asset = datasource.add_dataframe_asset(name="orders_silver")
batch_request = asset.build_batch_request(dataframe=orders_silver_df)
# resto do fluxo é idêntico ao Pandas
```

## Gerando Data Docs

```bash
great_expectations checkpoint run orders_silver_checkpoint
great_expectations docs build
```

Data Docs vira o "portal de qualidade" navegável — mostre isso para o data owner ao invés de
mandar logs brutos.

## Severidade por expectation (bloqueante vs quarantine)

GE não tem `severity` nativo por expectation — modele isso na camada de aplicação, agrupando
expectations em suites separadas por severidade:

```python
# Suite "orders_silver_suite" (bloqueante) — falha o pipeline
# Suite "orders_silver_suite_soft" (quarantine) — roteia para quarantine sem falhar

hard_result = context.run_checkpoint(checkpoint_name="orders_silver_checkpoint_hard")
if not hard_result.success:
    raise DataQualityError("Regra bloqueante violada")

soft_result = context.run_checkpoint(checkpoint_name="orders_silver_checkpoint_soft")
if not soft_result.success:
    send_to_quarantine(orders_df, reason="soft_expectation_failed", ...)
```

## Gotchas

- **GE não descarta registros automaticamente** — ele só reporta pass/fail. A ação (quarantine,
  fail, log) é responsabilidade do código que chama o checkpoint.
- **Suite versionada junto com o contrato** — mantenha a suite no mesmo repo/PR do
  `contracts/*.yaml` (ver `concepts/data-contracts-odcs.md`), senão elas divergem silenciosamente.
- **Rodar suite grande em todo batch tem custo** — em Spark, prefira sampling para expectations
  caras (ex.: regex em coluna de texto longo) e full-scan só para completude/unicidade.
- **Data Docs desatualizado é pior que não ter Data Docs** — automatize `docs build` no CI, não
  manualmente.
