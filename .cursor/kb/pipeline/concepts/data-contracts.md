# Data Contracts (Contratos de Dados)

## O que é

Acordo formal entre produtor e consumidor de dados, definindo schema, SLA e garantias de qualidade.
Baseado no padrão ODCS (Open Data Contract Standard).

## Estrutura ODCS-style YAML

```yaml
# data-contracts/orders-v1.yaml
id: "orders-contract-v1"
version: "1.0.0"

producer:
  team: data-engineering
  contact: data-team@company.com
  service: orders-pipeline

consumer:
  - team: analytics
    use_case: revenue-dashboard
  - team: ml-platform
    use_case: churn-model-features

schema:
  table: orders
  layer: silver
  fields:
    - name: order_id
      type: string
      required: true
      unique: true
      description: "Identificador único do pedido"
    - name: customer_id
      type: string
      required: true
    - name: amount
      type: decimal(10,2)
      required: true
      min: 0.01
      description: "Valor do pedido em BRL"
    - name: status
      type: string
      required: true
      enum: [pending, confirmed, shipped, delivered, cancelled]
    - name: created_at
      type: timestamp
      required: true

sla:
  freshness: "< 24 hours"
  availability: "> 99.5%"
  completeness: "> 99%"

quality:
  completeness: "> 99%"
  uniqueness:
    fields: [order_id]
    threshold: "100%"
  validity:
    amount_positive: "amount > 0"

versioning:
  breaking_change_policy: quarantine_and_notify
  backwards_compatible_changes: [add_nullable_column, widen_type]
  breaking_changes: [remove_column, rename_column, narrow_type, change_type]
```

## Como versionar contratos

- `v1.0.0 → v1.1.0`: mudança não-breaking (nova coluna nullable) — `mergeSchema`
- `v1.0.0 → v2.0.0`: mudança breaking (coluna removida, tipo mudou) — quarantine + ADR + notify

## Integração no pipeline

```python
from data_contracts import ContractValidator

contract = ContractValidator.load("data-contracts/orders-v1.yaml")
errors = contract.validate(silver_df)

if errors:
    # Registra na quarantine table com razão do erro
    quarantine_df = silver_df.withColumn("_quarantine_reason", lit(str(errors)))
    quarantine_df.write.mode("append").saveAsTable(config.quarantine_table())
    notify_owner(contract, errors, config)
    raise ContractViolationError(f"Contract {contract.id} violated: {errors}")
```

## Onde ficam os contratos

```
data-contracts/
├── orders-v1.yaml
├── customers-v1.yaml
└── products-v1.yaml
```

Versione junto com o código (mesma branch, mesmo PR).

## Integração Silver (checklist ODCS)

Após declarar o contrato, implemente a camada Silver com o checklist prescritivo:

- Pattern: [silver-checklist-odcs.md](../patterns/silver-checklist-odcs.md)
- Mapeie `schema.fields`, `quality`, `sla` e `versioning` → regras `SLV-*`
- Tipagem/cast permanecem no **Bronze**; Silver faz dedup, limpeza semântica e validação
- Severidade operacional: `fail` | `quarantine` | `log` (tabela de defaults no pattern)
- Gate mecânico do contrato: `DE-B003` — skill `de-conformidade`
