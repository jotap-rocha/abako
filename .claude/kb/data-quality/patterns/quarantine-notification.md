---
topic: quarantine-notification
confidence: null
mcp_validated: null
---

# Quarentena de Dados Inválidos + Notificação ao Owner

> Ver também: `pipeline/concepts/quarantine.md` e `pipeline/patterns/notification.md` —
> implementação de referência em Databricks/Delta (DDL da tabela, `_quarantine_*` columns,
> webhook Slack). Este arquivo cobre o padrão **agnóstico de ferramenta**: como conectar o
> resultado de Great Expectations/Soda/dbt tests ao fluxo de quarentena + notificação.

## O fluxo

```
Check de qualidade (GE / Soda / dbt test)
    ↓ falhou?
Classifica severidade (fail | quarantine | log)  ← definida no data contract
    ↓
    ├── fail       → aborta o pipeline, não escreve nada
    ├── quarantine → separa registros inválidos, escreve o resto, notifica owner
    └── log        → loga a violação, escreve tudo normalmente
```

## Adaptador: resultado de GE → quarantine

```python
def route_by_ge_result(df, checkpoint_result, config, run_id):
    if checkpoint_result.success:
        return df, None

    failed_expectations = [
        r["expectation_config"]["kwargs"]
        for r in checkpoint_result.list_validation_results()
        if not r["success"]
    ]

    invalid_mask = build_invalid_mask(df, failed_expectations)  # OR de todas as condições falhas
    valid_df = df.filter(~invalid_mask)
    invalid_df = df.filter(invalid_mask)

    if not invalid_df.isEmpty():
        send_to_quarantine(invalid_df, reason="ge_expectation_failed", run_id=run_id, config=config)
        notify_owner(config, anomaly_type="ge_expectation_failed",
                     details={"failed": failed_expectations, "count": invalid_df.count()},
                     run_id=run_id)

    return valid_df, invalid_df
```

## Adaptador: resultado de Soda → quarantine

```python
def route_by_soda_result(df, scan_results, config, run_id):
    failed_checks = [c for c in scan_results["checks"] if c["outcome"] == "fail"]
    if not failed_checks:
        return df

    # Soda reporta agregados, não linhas individuais — refaça o filtro a partir das condições
    invalid_condition = build_condition_from_checks(failed_checks)
    invalid_df = df.filter(invalid_condition)
    valid_df = df.filter(~invalid_condition)

    send_to_quarantine(invalid_df, reason="soda_check_failed", run_id=run_id, config=config)
    notify_owner(config, anomaly_type="soda_check_failed",
                 details={"checks": [c["name"] for c in failed_checks]}, run_id=run_id)
    return valid_df
```

## Adaptador: dbt test → quarantine (pós-processamento)

dbt tests não filtram linhas automaticamente — eles só reportam pass/fail no build. Para
quarentena, materialize a query do teste como uma tabela de "linhas que falharam":

```sql
-- models/quarantine/orders_quarantine.sql
{{ config(materialized='incremental') }}

SELECT *, 'invalid_amount' AS _quarantine_reason, current_timestamp() AS _quarantine_ts
FROM {{ ref('orders_silver') }}
WHERE amount <= 0

UNION ALL

SELECT *, 'orphan_customer' AS _quarantine_reason, current_timestamp() AS _quarantine_ts
FROM {{ ref('orders_silver') }} o
WHERE NOT EXISTS (SELECT 1 FROM {{ ref('customers_silver') }} c WHERE c.customer_id = o.customer_id)
```

```bash
dbt run --select orders_quarantine
# integre notify_owner() como on-run-end hook ou step separado no orquestrador
```

## Decidindo a severidade por dimensão

Regra prática — nem toda dimensão de `concepts/quality-dimensions.md` merece a mesma severidade:

| Dimensão violada | Severidade default | Racional |
|---|---|---|
| Completude em PK | `fail` | Sem chave, o registro é inutilizável |
| Unicidade em PK | `quarantine` | Investigável; pode ser retry duplicado da fonte |
| Validade (range/enum) | `quarantine` | Registro é usável parcialmente; isola o suspeito |
| Consistência cross-field | `quarantine` | Requer investigação, não é erro binário óbvio |
| Atualidade (freshness) | `log` + alerta | Não há "linha" para quarentenar — é sinal de pipeline |

## Notificação — payload mínimo

Independente da ferramenta de origem (GE/Soda/dbt), a notificação ao owner deve conter:
`anomaly_type`, `contract_id`, `dimension`, `count`, `run_id`, `quarantine_table` (se aplicável).
Isso permite ao owner agir sem abrir logs — ver payload completo em
`pipeline/patterns/notification.md`.

## Gotchas

- **Quarentena sem prazo de retenção vira lixo permanente** — declare TTL/expurgo na tabela de
  quarantine, senão ela cresce sem controle e ninguém revisita registros antigos.
- **Notificar toda violação individual gera alert fatigue** — agregue por `run_id` + `reason`
  antes de notificar (uma mensagem por anomalia, não uma por linha).
- **`log` sem alerta associado é dado morto** — se a severidade é `log`, ainda assim configure
  um alerta de threshold (ex.: `> 5% das linhas logadas em 1h`), senão ninguém nunca olha o log.
