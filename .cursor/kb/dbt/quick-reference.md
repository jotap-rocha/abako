---
domain: dbt
topic: quick-reference
---

# dbt — Quick Reference

### Layout canônico

```
project/
├── dbt_project.yml          ← config global, defaults de materialization por pasta
├── dependencies.yml          ← packages + projetos upstream (dbt Mesh)
├── models/
│   ├── staging/               ← 1:1 com fonte, view, cast + rename apenas
│   │   └── stg_orders.sql
│   ├── intermediate/          ← lógica de junção/transform, ephemeral
│   │   └── int_orders_joined.sql
│   ├── marts/                 ← fato/dimensão final, table ou incremental
│   │   ├── fct_orders.sql
│   │   └── _orders__models.yml   ← schema.yml: tests, descriptions, contracts
├── snapshots/                ← SCD Type 2, roda separado (`dbt snapshot`)
├── macros/
│   └── generic_tests/         ← 1 arquivo por generic test custom
├── tests/                    ← singular tests
└── seeds/                    ← CSV pequeno versionado (lookup tables)
```

### Invariantes

| # | Invariante |
|---|---|
| DBT-01 | Toda tabela final (`marts/`) tem `unique_key` testado (`unique` + `not_null`) |
| DBT-02 | Incremental model sempre filtra por coluna de última atualização, com `coalesce` de fallback no primeiro run |
| DBT-03 | `ref()`/`source()` sempre — nunca nome de tabela hardcoded no SQL |
| DBT-04 | Model público de Mesh (`access: public`) tem `contract.enforced: true` |
| DBT-05 | Snapshot roda em job separado do `dbt run`/`dbt build` normal — confirmar orquestração |
| DBT-06 | Generic test custom tem 1 caso de teste manual comprovando que ele falha quando deveria |

### Decision tree: materialization

```
Consultado fora do dbt (BI, API) com frequência/volume alto?
    ├── SIM → table (ou incremental se volume/histórico grande)
    └── NÃO → view (staging) ou ephemeral (passo intermediário só)

Volume alto + histórico maior que a janela de mudança?
    └── incremental — ver incremental-strategies.md p/ escolher a strategy:
        append (fonte append-only) | merge (upsert por unique_key)
        | delete+insert (refresh por partição) | microbatch (fatos massivos + late data)
```

### Comandos essenciais

```bash
dbt build                        # run + test + snapshot + seed, respeitando o DAG
dbt run --select fct_orders+     # roda o model e tudo downstream
dbt run --select +fct_orders     # roda o model e tudo upstream (dependências)
dbt test --select "test_type:generic"
dbt run --full-refresh --select fct_orders   # reconstrói do zero (incremental)
dbt snapshot                     # roda snapshots (fora do dbt run normal)
dbt sl query --metrics revenue --group-by metric_time__month
```
