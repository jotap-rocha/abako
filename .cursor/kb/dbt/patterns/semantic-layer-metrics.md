# Padrão: Semantic Layer (Métricas)

## Quando usar

Múltiplas ferramentas de BI (Sigma, Hex, Tableau) ou consumidores diferentes precisam da
**mesma definição de métrica** ("revenue", "active users") sem reimplementar a lógica de
agregação em cada dashboard — a definição vive uma vez no dbt, é consumida via
MetricFlow/dbt Semantic Layer.

## Passo 1 — semantic model (mapeia um model para entidades/dimensões/measures)

```yaml
# models/marts/_orders__semantic.yml
semantic_models:
  - name: orders
    description: "Grão: um registro por pedido."
    model: ref('fct_orders')
    defaults:
      agg_time_dimension: metric_time

    entities:
      - name: order_id
        type: primary
      - name: customer
        type: foreign
        expr: customer_id

    dimensions:
      - name: metric_time
        expr: cast(ordered_at as date)
        type: time
        type_params: {time_granularity: day}
      - name: status
        type: categorical

    measures:
      - name: order_total
        agg: sum
        expr: amount
      - name: order_count
        agg: count
        expr: order_id
```

## Passo 2 — metric (combina measures em uma definição nomeada)

```yaml
# models/marts/_orders__metrics.yml
metrics:
  - name: revenue
    description: "Soma do total dos pedidos."
    type: simple
    label: Revenue
    type_params:
      measure: order_total

  - name: avg_order_value
    type: ratio
    label: "Ticket médio"
    type_params:
      numerator: order_total
      denominator: order_count
```

## Passo 3 — consultar via CLI (validação local)

```bash
dbt sl query --metrics revenue --group-by metric_time__month
dbt sl list dimensions --metrics revenue
```

## Passo 4 — consumir de uma ferramenta BI (ex.: Sigma)

```sql
select *
from {{
  semantic_layer.query(
    metrics=['revenue', 'order_count', 'avg_order_value'],
    group_by=[Dimension('metric_time').grain('day')]
  )
}}
```

## Filtro por métrica (ref-metrics-in-filters)

```bash
dbt sl query --metrics accounts --where "{{ Metric('data_model_runs', group_by=['account']) }} > 5"
```

## SCD Type 2 como dimensão temporal (join correto com validade)

Quando a dimensão tem histórico (ver `patterns/snapshot-scd2.md`), declarar
`validity_params` para o MetricFlow fazer o join respeitando a janela de validade —
sem isso, métrica por dimensão "tier do cliente" usaria sempre o valor atual, mesmo
para eventos passados.

```yaml
dimensions:
  - name: tier_start
    type: time
    expr: start_date
    type_params:
      time_granularity: day
      validity_params: {is_start: true}
  - name: tier_end
    type: time
    expr: end_date
    type_params:
      time_granularity: day
      validity_params: {is_end: true}
```

## Cross-project — métrica consumindo model de outro projeto (dbt Mesh)

```yaml
semantic_models:
  - name: customer_orders
    model: ref('jaffle_finance', 'fct_orders')   # ref('project', 'model')
```

## Checklist

- [ ] Toda metric tem `description` — é a documentação que aparece nas ferramentas de BI
- [ ] `agg_time_dimension` declarado no `defaults` do semantic model, não implícito
- [ ] Métricas `ratio`/`derived` reusam measures existentes em vez de reescrever SQL
- [ ] Dimensões SCD2 usam `validity_params` para join temporal correto
- [ ] Validado com `dbt sl query` localmente antes de expor na ferramenta de BI
