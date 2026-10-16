---
topic: dlt-quarantine
confidence: null
mcp_validated: null
---

# Pattern: DLT com quarentena versionada

## Quando usar

Pipeline com sinal DLT + expectations — fechar **DE-D003** sem API live.
Referência: `examples/databricks-dlt-min/`.

## Layout alvo

```text
project/
├── databricks.yml                      # DE-D001
├── config/
│   ├── pipeline.yaml
│   ├── quarantine-policy.yaml          # DE-D003
│   └── schema-rescue-policy.yaml       # DE-D004
├── pipelines/
│   └── orders_dlt.py                   # import dlt / @dlt. + expectations
├── uc/
│   ├── grants.yaml
│   └── lineage.md
└── tests/
```

## Política mínima (ilustrativa)

```yaml
quality:
  invalid_records: quarantine_orders
  quarantine_table: ops.quarantine_orders
  on_expectation_fail: quarantine
```

## Passos

1. Stub DLT com pelo menos uma expectation.
2. Versionar destino de quarentena no YAML (não só comentário no código).
3. Completar D001 + D004 + D005.
4. `python -m config.canonical_data_check validate <path>` — **DE-D002** skip sem SDP.

## Anti-padrões

- Expectation sem destino de quarentena documentado.
- Quarentena “só no workspace” sem arquivo no repo.
- Waiver sem owner/expiry (ver skill `de-conformidade`).

## Ver também

- Concept: [dlt-quarantine-expectations.md](../concepts/dlt-quarantine-expectations.md)
- Example: `examples/databricks-dlt-min/config/quarantine-policy.yaml`
