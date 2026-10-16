---
topic: dbt-tests
confidence: null
mcp_validated: null
---

# Testes de Dados no dbt (schema tests + custom tests)

## Quando usar

dbt tests quando o projeto já usa dbt para transformação — o teste vive junto do modelo,
versionado no mesmo PR, sem infra extra. Fraco em observabilidade contínua fora de um `dbt run`
(comparar com Soda para monitoramento standalone).

## Schema tests (built-in, genéricos)

```yaml
# models/silver/schema.yml
models:
  - name: orders_silver
    columns:
      - name: order_id
        tests:
          - not_null          # completude
          - unique            # unicidade
      - name: customer_id
        tests:
          - not_null
          - relationships:    # consistência cross-tabela
              to: ref('customers_silver')
              field: customer_id
      - name: status
        tests:
          - accepted_values:  # validade
              values: ['pending', 'confirmed', 'shipped', 'delivered', 'cancelled']
      - name: amount
        tests:
          - dbt_utils.accepted_range:   # validade — requer pacote dbt-utils
              min_value: 0.01
```

## Source freshness (atualidade)

```yaml
# models/staging/sources.yml
sources:
  - name: raw_orders
    freshness:
      warn_after: {count: 12, period: hour}
      error_after: {count: 24, period: hour}
    loaded_at_field: _ingested_at
    tables:
      - name: orders
```

```bash
dbt source freshness
```

Esse comando é o equivalente dbt-nativo ao check de `concepts/pipeline-observability.md`
(pilar Freshness) — não precisa de ferramenta externa se o projeto já usa dbt.

## Custom generic tests (reutilizáveis)

```sql
-- tests/generic/test_positive_value.sql
{% test positive_value(model, column_name) %}
SELECT *
FROM {{ model }}
WHERE {{ column_name }} <= 0
{% endtest %}
```

```yaml
# uso no schema.yml
columns:
  - name: amount
    tests:
      - positive_value
```

## Singular tests (regra específica, não reutilizável)

```sql
-- tests/singular/assert_no_future_dates.sql
SELECT *
FROM {{ ref('orders_silver') }}
WHERE created_at > current_timestamp()
```

Um singular test **falha se a query retornar qualquer linha** — o teste É a query de detecção.

## Pacote dbt-expectations (Great Expectations no dbt)

```bash
# packages.yml
packages:
  - package: calogica/dbt_expectations
    version: [">=0.10.0", "<0.11.0"]
```

```yaml
columns:
  - name: amount
    tests:
      - dbt_expectations.expect_column_values_to_be_between:
          min_value: 0.01
          max_value: 1000000
      - dbt_expectations.expect_column_mean_to_be_between:
          min_value: 10
          max_value: 500
```

Portabiliza boa parte do vocabulário de expectations do Great Expectations para dentro do dbt.

## Severidade (warn vs error)

```yaml
columns:
  - name: customer_id
    tests:
      - not_null:
          config:
            severity: warn        # loga, não quebra o build
            warn_if: ">10"        # warn só se > 10 violações
            error_if: ">100"      # error se > 100 violações
```

## Rodando

```bash
dbt test                      # roda todos os testes
dbt test --select orders_silver   # só os testes do modelo
dbt build                     # roda modelo + testes na mesma execução (fail-fast por nó)
```

## Gotchas

- **`dbt build` versus `dbt run` + `dbt test`** — `dbt build` para a build de um nó se o teste
  dele falhar antes de rodar os downstream; `dbt run` seguido de `dbt test` roda tudo antes de
  testar, propagando dado ruim para modelos dependentes.
- **`relationships` test é caro em tabelas grandes** — é um `LEFT JOIN` completo; considere
  amostragem ou rodar só em ambiente de CI com dataset reduzido.
- **Severity `warn` não bloqueia deploy** — se o pipeline de CI não falha em `warn`, o time para
  de olhar os warnings. Trate acúmulo de warnings como dívida técnica com revisão periódica.
- **Teste em `source` (não em `model`)** exige `dbt test --select source:raw_orders` — teste de
  source não roda automaticamente com `dbt test` sem seleção.
