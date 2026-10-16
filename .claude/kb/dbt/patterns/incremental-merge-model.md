# Receita: Incremental Model com Merge

## Quando usar

Fato/dimensão grande, com registros que sofrem update na origem (ex.: pedido muda de
status), volume alto o bastante para tornar `materialized='table'` caro em cada run.

## Receita completa

```sql
-- models/marts/fct_orders.sql
{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key='order_id',
    merge_update_columns=['status', 'amount', 'updated_at'],
    on_schema_change='append_new_columns',
) }}

with source as (

    select
        order_id,
        customer_id,
        status,
        amount,
        created_at,
        updated_at
    from {{ source('erp', 'orders') }}

    {% if is_incremental() %}
    -- só reprocessa o que mudou desde o último run — não é full scan
    where updated_at > (select coalesce(max(updated_at), '1900-01-01') from {{ this }})
    {% endif %}

)

select * from source
```

## Passo a passo

1. **`unique_key`** — obrigatório para merge. Identifica qual linha existente é
   atualizada vs qual é inserida. Pode ser lista (`unique_key=['order_id', 'line_id']`)
   para grão composto.
2. **Filtro incremental** — sempre usar a coluna de "última atualização" da fonte
   (`updated_at`), nunca `created_at` (perderia updates de registros antigos).
3. **`coalesce(max(...), '1900-01-01')`** — evita erro no primeiro run, quando `{{ this
   }}` ainda não existe com dados (subquery retorna NULL).
4. **`merge_update_columns`** — restringe quais colunas são sobrescritas no match. Evita
   sobrescrever `created_at` (deveria ser imutável) mesmo que venha no select.
5. **`on_schema_change`** — decide o que fazer se a fonte ganhar/remover coluna:
   `ignore` (default) | `fail` | `append_new_columns` | `sync_all_columns`.

## Full refresh seguro

```bash
# reconstroi a tabela inteira do zero — usar quando:
# 1) mudou a lógica de negócio do model, 2) mudou incremental_strategy,
# 3) suspeita de drift entre incremental e full scan
dbt run --select fct_orders --full-refresh
```

## Validando consistência incremental vs full

```sql
-- tests/singular/assert_fct_orders_incremental_matches_full.sql
-- roda manualmente após mudança de lógica, não em CI (caro)
with incremental_totals as (
    select customer_id, sum(amount) as total from {{ ref('fct_orders') }} group by 1
),
full_scan_totals as (
    select customer_id, sum(amount) as total
    from {{ source('erp', 'orders') }}
    group by 1
)
select i.customer_id, i.total as incremental_total, f.total as full_total
from incremental_totals i
join full_scan_totals f on i.customer_id = f.customer_id
where abs(i.total - f.total) > 0.01
```

## Anti-padrões

```sql
-- ERRADO: unique_key ausente com incremental_strategy='merge' — dbt levanta erro
{{ config(materialized='incremental', incremental_strategy='merge') }}
select * from {{ source('erp', 'orders') }}

-- ERRADO: filtro incremental usando created_at — nunca pega updates
{% if is_incremental() %}
where created_at > (select max(created_at) from {{ this }})
{% endif %}

-- ERRADO: sem coalesce no primeiro run — subquery contra tabela vazia quebra o filtro
where updated_at > (select max(updated_at) from {{ this }})
```

## Checklist

- [ ] `unique_key` reflete o grão real da tabela (single ou composto)
- [ ] Filtro incremental usa coluna de última atualização, com `coalesce` de fallback
- [ ] `merge_update_columns` ou `merge_exclude_columns` declarado explicitamente
- [ ] `on_schema_change` definido (não deixar no default silencioso se schema muda com
      frequência)
- [ ] Teste `unique` + `not_null` no `unique_key` via `schema.yml`
- [ ] Full-refresh testado localmente antes de rodar em produção pela primeira vez
