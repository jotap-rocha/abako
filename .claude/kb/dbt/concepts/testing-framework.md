# Framework de Testes (Generic + Singular)

## O que é

dbt tem dois tipos de `data_tests`: **generic** (parametrizados, reutilizáveis entre
models/colunas) e **singular** (uma query SQL específica, uso único). Ambos seguem a
mesma regra: **o teste falha se a query retornar alguma linha**.

## Generic tests

- Definidos como macro `{% test nome(model, column_name, ...) %}`.
- Aplicados declarativamente em `schema.yml`, reutilizados em N colunas/models.
- 4 tests built-in: `unique`, `not_null`, `accepted_values`, `relationships`.

```yaml
models:
  - name: orders
    columns:
      - name: order_id
        data_tests:
          - unique
          - not_null
      - name: status
        data_tests:
          - accepted_values:
              arguments:
                values: ['placed', 'shipped', 'completed', 'returned']
      - name: customer_id
        data_tests:
          - relationships:
              arguments:
                to: ref('customers')
                field: id
```

## Singular tests

- Um arquivo `.sql` em `tests/` — a query em si é o teste, sem parametrização.
- Usado para regra de negócio específica que não se repete: "receita nunca é negativa",
  "soma de itens do pedido bate com o total do pedido".

```sql
-- tests/assert_order_total_matches_items.sql
select o.order_id
from {{ ref('orders') }} o
join (
    select order_id, sum(amount) as items_total
    from {{ ref('order_items') }}
    group by 1
) i on o.order_id = i.order_id
where o.total != i.items_total
```

## Executar por tipo

```bash
dbt test --select "test_type:generic"    # só os generic
dbt test --select "test_type:singular"   # só os singular
dbt test --select "test_type:data"       # generic + singular, sem unit tests
dbt test --select "test_type:unit"       # só unit tests
```

## severity: error vs warn

- Default: `severity: error` — falha o `dbt build`/`dbt test`.
- `severity: warn` — loga mas não quebra o pipeline. Usar para regras "suspeitas" ainda
  não validadas em produção, nunca para invariantes de negócio.

```yaml
data_tests:
  - accepted_values:
      arguments: {values: ['blue', 'red']}
      config:
        severity: warn
```

## Custom generic test (base para patterns/custom-generic-tests.md)

```sql
{% test is_even(model, column_name) %}
with validation as (
    select {{ column_name }} as even_field from {{ model }}
)
select * from validation where (even_field % 2) = 1
{% endtest %}
```

## Unit tests (dbt >= 1.8)

- Testam a **lógica SQL do model** com dados mockados de input — diferente de data tests,
  que testam os **dados reais** já materializados.
- `given` (input mockado) + `expect` (output esperado), formatos `dict | csv | sql`.

```yaml
unit_tests:
  - name: test_discount_logic
    model: stg_orders
    given:
      - input: ref('raw_orders')
        format: csv
        rows: |
          id,amount
          1,100
    expect:
      format: dict
      rows:
        - {id: 1, amount_with_discount: 90}
```

## Gotchas

- Generic test que retorna 0 linhas = passou; se a query tiver erro de sintaxe silencioso
  (ex.: `join` errado que nunca bate) o teste "passa" mas não testa nada — sempre valide
  o teste com um caso que deveria falhar.
- `relationships` sem `not_null` na FK deixa `NULL` passar silenciosamente (NULL não viola
  FK em SQL) — declare os dois juntos quando a FK é obrigatória.
- Unit tests rodam sobre o SQL compilado, não sobre dado real do warehouse — não
  substituem data tests em produção, são complementares (lógica vs dado).
