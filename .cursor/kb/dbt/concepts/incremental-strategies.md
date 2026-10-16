# Estratégias de Incremental Load

## O que é

Quando `materialized='incremental'`, `incremental_strategy` define **como** as linhas
novas (resultado do select filtrado por `is_incremental()`) são combinadas com a tabela
já existente. A estratégia certa depende do padrão de mudança da fonte.

## append

- **Comportamento**: só insere as linhas novas — nunca atualiza nem deleta.
- **Quando usar**: fonte é estritamente append-only (eventos, logs, cliques).
- **Risco**: se a fonte reenviar uma linha já processada, gera duplicata — não há
  dedup automática.

```sql
{{ config(materialized='incremental', incremental_strategy='append') }}
select * from {{ ref('events') }}
{% if is_incremental() %}
where event_ts > (select max(event_ts) from {{ this }})
{% endif %}
```

## merge

- **Comportamento**: upsert — atualiza linhas existentes (match por `unique_key`) e
  insere as novas. Requer `unique_key` obrigatório.
- **Quando usar**: dimensões e fatos que sofrem `UPDATE` na origem (status de pedido,
  saldo de conta).
- **Refinamento**: `merge_update_columns` / `merge_exclude_columns` para limitar quais
  colunas são atualizadas no match.

```sql
{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key='account_id',
    merge_update_columns=['balance', 'last_updated']
) }}
select account_id, balance, last_updated from {{ source('core', 'accounts') }}
{% if is_incremental() %}
where last_updated > (select max(last_updated) from {{ this }})
{% endif %}
```

## delete+insert

- **Comportamento**: deleta as linhas cujo `unique_key` bate com o novo lote, depois
  insere o lote inteiro. Alternativa ao merge em warehouses sem `MERGE` nativo eficiente.
- **Quando usar**: refresh completo de uma partição/dia específico — comum em
  full-refresh parcial por partição.

```sql
{{ config(
    materialized='incremental',
    unique_key='id',
    incremental_strategy='delete+insert'
) }}
select * from source_table
{% if is_incremental() %}
where updated_at > (select max(updated_at) from {{ this }})
{% endif %}
```

## microbatch

- **Comportamento**: processa a fonte em lotes fixos de tempo (`batch_size`: hour/day/
  month), cada lote roda como uma transação independente. Reprocessa automaticamente
  `lookback` lotes anteriores para pegar dados atrasados (late-arriving data).
- **Quando usar**: tabelas de fatos massivas com histórico multi-ano — troca um único
  `is_incremental()` monolítico por N transações pequenas, com retry por lote.
- **Config obrigatória**: `event_time` (coluna de tempo do evento) + `batch_size`.

```sql
{{ config(
    materialized='incremental',
    incremental_strategy='microbatch',
    event_time='event_occurred_at',
    batch_size='day',
    lookback=3,
    begin='2020-01-01'
) }}
select * from {{ ref('stg_events') }}  -- filtro por batch é automático, sem is_incremental()
```

## Comparação rápida

| Estratégia | Precisa `unique_key`? | Dedup automática | Melhor para |
|---|---|---|---|
| append | Não | Não | Eventos estritamente append-only |
| merge | Sim | Sim (via key) | Dimensões/fatos com update |
| delete+insert | Sim | Sim (via key) | Refresh por partição/lote |
| microbatch | Recomendado | Por lote | Fatos massivos com late data |

## Gotchas

- `merge` sem suporte nativo de `MERGE` no warehouse cai para `delete+insert` internamente
  em alguns adapters — checar a doc do adapter específico.
- `microbatch` ignora `is_incremental()` manual — o filtro de tempo é automático a partir
  de `event_time`; não adicione um `where` redundante.
- Mudar de estratégia entre runs (ex.: append → merge) pode exigir `--full-refresh` para
  reconstruir a tabela do zero — misturar estratégias no histórico gera inconsistência.
- `lookback` em microbatch reprocessa lotes já processados — idempotência do select é
  obrigatória (sem `random()`, sem side effects).
