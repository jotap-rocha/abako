---
topic: data-contracts-odcs
confidence: null
mcp_validated: null
---

# Data Contracts — ODCS (Open Data Contract Standard)

> Ver também: `pipeline/concepts/data-contracts.md` — versão simplificada, YAML custom,
> focada em `schema` + `quality` para pipelines Medallion. Este arquivo aprofunda a estrutura
> ao estilo ODCS (spec aberta mantida pela comunidade Bitol/Linux Foundation) e o ciclo de vida
> do contrato como artefato versionado entre produtor e consumidor.

## O que é ODCS

Especificação aberta para descrever um contrato de dados de forma padronizada e portável entre
ferramentas (data catalogs, pipelines, testes). Um contrato ODCS não é só schema — é o
acordo completo: **quem produz, quem consome, o que é garantido, e o que quebra o contrato**.

## Estrutura conceitual (simplificada)

```yaml
# contracts/orders-v2.yaml — estrutura inspirada no ODCS
apiVersion: v1
kind: DataContract
id: orders-contract
version: "2.0.0"
status: active   # draft | active | deprecated | retired

description:
  purpose: "Pedidos confirmados para dashboards de revenue e modelo de churn"
  domain: sales

producer:
  team: data-engineering
  contact: data-team@company.com
  system: orders-pipeline

consumers:
  - team: analytics
    use_case: revenue-dashboard
    access: read-only
  - team: ml-platform
    use_case: churn-model-features
    access: read-only

schema:
  physical: orders_silver
  logical:
    - name: order_id
      type: string
      required: true
      unique: true
      classification: internal
    - name: customer_id
      type: string
      required: true
      classification: pii-indirect   # não é PII direto, mas permite join com PII
    - name: amount
      type: decimal(10,2)
      required: true

sla:
  freshness: "< 24h"
  availability: "> 99.5%"
  support_hours: "business-hours"

quality:
  - dimension: completeness
    rule: "order_id IS NOT NULL"
    threshold: "> 99%"
  - dimension: uniqueness
    rule: "order_id"
    threshold: "100%"
  - dimension: validity
    rule: "amount > 0"
    threshold: "100%"

lifecycle:
  breaking_change_policy: "major version bump + 30 days deprecation window"
  non_breaking_changes: [add_nullable_field, widen_type, add_consumer]
  breaking_changes: [remove_field, rename_field, narrow_type, change_semantics]
```

## Diferença chave vs contrato "simples"

| Item | Contrato simples (pipeline/) | ODCS-style (este arquivo) |
|---|---|---|
| Producer/consumer | opcional | obrigatório, com `use_case` declarado |
| Status do contrato | não modelado | `draft/active/deprecated/retired` |
| Classificação de dado | não modelado | `classification` por campo (PII, internal) |
| Ciclo de vida | ad-hoc | `lifecycle` com política de breaking change formal |

## Contract testing no CI

O contrato é código — valide o schema real contra o contrato declarado em todo PR/merge, antes
do deploy, não só em runtime do pipeline.

```python
# ci/validate_contract.py
from contract_lib import load_contract, diff_schema

contract = load_contract("contracts/orders-v2.yaml")
actual_schema = introspect_table("orders_silver")

diff = diff_schema(expected=contract.schema.logical, actual=actual_schema)

if diff.has_breaking_changes():
    raise ContractBreakingChangeError(
        f"Breaking change detectado: {diff.breaking}. "
        f"Requer bump de major version + deprecation window de 30 dias."
    )
```

## Onde o contrato ODCS se conecta neste domínio

- Os campos de `quality:` mapeiam para as dimensões de `concepts/quality-dimensions.md`.
- O `sla.freshness` é o input do check de atualidade em `concepts/pipeline-observability.md`.
- A violação de contrato aciona `patterns/quarantine-notification.md`.

## Gotchas

- **Versão do contrato ≠ versão do pipeline** — o contrato versiona o *dado exposto*, o pipeline
  versiona o *código*. Podem evoluir em ritmos diferentes.
- **`classification` não é opcional em campo que pode conter PII indireto** — join keys que
  permitem reidentificação (ex.: `customer_id`) devem ser classificadas mesmo sem PII direto.
- **Breaking change sem deprecation window quebra consumer silenciosamente** — sempre declare
  a janela no `lifecycle.breaking_change_policy`.
