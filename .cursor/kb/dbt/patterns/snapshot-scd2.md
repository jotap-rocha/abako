# Padrão: Snapshot para SCD Type 2

## Quando usar

Precisa reconstituir o **estado histórico** de uma dimensão que muda ao longo do tempo
(preço de produto, tier de cliente, endereço) — não só o valor atual, mas "qual era o
valor entre a data X e a data Y".

## Receita — strategy timestamp (fonte tem `updated_at` confiável)

```sql
-- snapshots/customers_snapshot.sql
{% snapshot customers_snapshot %}

{{
  config(
    target_schema='snapshots',
    unique_key='customer_id',
    strategy='timestamp',
    updated_at='updated_at',
  )
}}

select
    customer_id,
    tier,
    email,
    updated_at
from {{ source('crm', 'customers') }}

{% endsnapshot %}
```

## Receita — strategy check (sem `updated_at` confiável)

Compara colunas explicitamente a cada run para detectar mudança — mais caro, mas não
depende de a fonte manter timestamp correto.

```sql
{% snapshot orders_snapshot %}

{{
  config(
    target_schema='snapshots',
    unique_key='order_id',
    strategy='check',
    check_cols=['status', 'is_cancelled'],
  )
}}

select order_id, status, is_cancelled from {{ ref('stg_orders') }}

{% endsnapshot %}
```

Ou `check_cols='all'` para comparar todas as colunas — simples, mas gera novo registro
de histórico em qualquer mudança, inclusive campos irrelevantes para o negócio.

## Colunas geradas pelo dbt

| Coluna | Significado |
|---|---|
| `dbt_valid_from` | Timestamp em que esta versão do registro passou a valer |
| `dbt_valid_to` | Timestamp em que deixou de valer (`NULL` = versão atual) |
| `dbt_scd_id` | Hash único da versão — chave primária técnica do snapshot |
| `dbt_updated_at` | Timestamp do run que gerou/atualizou esta linha |

Resultado após duas mudanças de `status`:

```text
id | status  | dbt_valid_from   | dbt_valid_to
1  | pending | 2024-01-01 10:47 | 2024-01-01 11:05
1  | shipped | 2024-01-01 11:05 | 2024-01-01 11:20
1  | deleted | 2024-01-01 11:20 |
```

## Hard deletes

Por padrão, dbt ignora deleções na origem (`hard_deletes='ignore'`). Para tracking
completo de SCD2, capturar exclusão como um evento:

```sql
{{ config(
    target_schema='snapshots',
    unique_key='id',
    strategy='timestamp',
    updated_at='updated_at',
    hard_deletes='new_record',   -- gera linha com dbt_is_deleted=True
) }}
```

## Consumindo o snapshot com join temporal

```sql
-- fct_metric às dimensões válidas no momento do evento
select
    e.metric_time,
    e.dimensions_1,
    sum(1) as num_events
from {{ ref('events') }} e
left join {{ ref('customers_snapshot') }} s
    on e.customer_id = s.customer_id
    and e.metric_time >= s.dbt_valid_from
    and (e.metric_time < s.dbt_valid_to or s.dbt_valid_to is null)
group by 1, 2
```

## Agendamento — snapshot roda separado do build normal

```bash
dbt snapshot                          # roda só os snapshots
dbt build --resource-type snapshot    # idem, via build
```

`dbt run`/`dbt build` sem flag específica **não** re-executa snapshots automaticamente
em todas as versões — confirme a orquestração externa (Airflow/dbt Cloud job) inclui
`dbt snapshot` no schedule certo (normalmente antes do `dbt run` dos models que
dependem dele).

## Gotchas

- Snapshot não é idempotente para full-refresh comum — apagar e recriar destrói o
  histórico. Fazer backup (`create table ... as select * from snapshot`) antes de
  qualquer mudança estrutural.
- `strategy='check'` com `check_cols='all'` inclui colunas técnicas (`_loaded_at`) se
  elas estiverem no select — declare `check_cols` explícito para dimensões de negócio.
- Snapshot precisa rodar com frequência suficiente para capturar mudanças transitórias —
  se o status mudar duas vezes entre dois runs, a versão intermediária se perde.
