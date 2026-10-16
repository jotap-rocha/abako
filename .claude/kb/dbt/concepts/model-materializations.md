# Tipos de Model (Materializations)

## O que é

`materialized` define como o `select` de um model vira objeto no data warehouse.
Configurado em `dbt_project.yml` (default por diretório) ou via `config()` no próprio model.

## As 4 materializations principais

### view
- **O que faz**: cria uma `CREATE VIEW` — sem armazenamento próprio, recalcula a cada query.
- **Quando usar**: staging models, lógica leve, dado que muda com frequência.
- **Custo**: zero storage, custo de compute a cada leitura.

```sql
{{ config(materialized='view') }}
select * from {{ source('raw', 'orders') }}
```

### table
- **O que faz**: `CREATE TABLE AS SELECT` — recria a tabela inteira a cada `dbt run`.
- **Quando usar**: marts finais, dashboards, dado que exige leitura rápida e repetida.
- **Custo**: storage full + reprocessamento completo a cada run (full refresh sempre).

```sql
{{ config(materialized='table') }}
select customer_id, sum(amount) as total from {{ ref('stg_orders') }} group by 1
```

### incremental
- **O que faz**: processa apenas linhas novas/alteradas desde o último run; usa
  `is_incremental()` para filtrar o select. Ver `incremental-strategies.md` para as
  estratégias de merge dos dados novos na tabela existente.
- **Quando usar**: tabelas grandes (fatos, eventos) onde reprocessar tudo é caro.
- **Custo**: baixo por run, mas exige lógica de filtro correta — bug aqui gera gaps ou
  duplicatas silenciosas.

```sql
{{ config(materialized='incremental', unique_key='id') }}
select id, amount from {{ ref('raw_orders') }}
{% if is_incremental() %}
where id > (select max(id) from {{ this }})
{% endif %}
```

### ephemeral
- **O que faz**: não materializa nada no warehouse — é inlined como CTE em quem faz `ref()`
  dela. Existe só durante a compilação.
- **Quando usar**: lógica intermediária reutilizável (dedup, cast) que não precisa ser
  consultada isoladamente.
- **Custo**: zero storage, mas CTEs aninhadas demais degradam legibilidade e podem
  degradar performance de compilação em cadeias longas.

```sql
{{ config(materialized='ephemeral') }}
select *, row_number() over (partition by id order by updated_at desc) as rn
from {{ source('raw', 'customers') }}
```

## Configurar default por diretório

```yaml
# dbt_project.yml
models:
  jaffle_shop:
    staging:
      +materialized: view
    intermediate:
      +materialized: ephemeral
    marts:
      +materialized: table
```

## Decision tree

```
O model é consultado fora do dbt (BI tool, API)?
  ├── SIM, e é pesado/lido com frequência → table
  ├── SIM, mas é leve/staging → view
  └── NÃO, é só um passo intermediário → ephemeral

O model tem volume alto e histórico maior que a janela de mudança?
  └── SIM → incremental (ver incremental-strategies.md p/ escolher estratégia)
```

## Gotchas

- `ephemeral` não aparece no warehouse — não dá para debugar com `select * from` direto;
  use `dbt show` ou `--select` isolado durante desenvolvimento.
- `table` sempre reprocessa tudo — não confundir com `incremental`: uma tabela grande com
  `materialized='table'` recria do zero a cada `dbt run`, mesmo sem mudança nos dados.
- Trocar `view` → `table` (ou vice-versa) exige `--full-refresh` explícito ou o objeto
  antigo precisa ser dropado manualmente; dbt não troca o tipo de objeto sozinho em todos
  os adapters.
- `incremental` sem `unique_key` normalmente vira append-only (depende da strategy
  default do adapter) — duplicatas se a fonte reenviar linhas já processadas.
