# Padrões de Macro

## Quando escrever uma macro

Lógica SQL/Jinja repetida em 3+ models, ou lógica condicional por adapter
(Snowflake vs BigQuery vs Postgres) que precisa de um único ponto de manutenção.

## Macro utilitária simples (transformação de coluna)

```sql
-- macros/cents_to_dollars.sql
{% macro cents_to_dollars(column_name, scale=2) %}
    ({{ column_name }} / 100)::numeric(16, {{ scale }})
{% endmacro %}
```

```sql
select {{ cents_to_dollars('amount_cents') }} as amount from {{ ref('stg_orders') }}
```

## Macro com retorno de valor (não SQL) — `return()`

Use `return()` quando a macro deve devolver um valor Python (lista, string, número) para
ser usado em Jinja, não SQL renderizado diretamente.

```sql
{% macro cartesian_product(list1, list2) %}
    {% set result = [] %}
    {% for item1 in list1 %}
        {% for item2 in list2 %}
            {% set _ = result.append((item1, item2)) %}
        {% endfor %}
    {% endfor %}
    {{ return(result) }}
{% endmacro %}
```

## Dispatch — macro que se comporta diferente por adapter

Padrão usado internamente pelo dbt-utils: uma macro "roteadora" chama a implementação
específica do adapter atual (`default__` como fallback).

```sql
-- macros/generate_pointer_alias.sql
{% macro generate_pointer_alias(custom_alias_name=none, node=none) %}
    {{ return(adapter.dispatch('generate_pointer_alias', 'my_project')(custom_alias_name, node)) }}
{% endmacro %}

{% macro default__generate_pointer_alias(custom_alias_name, node) %}
    {{ custom_alias_name or node.name }}
{% endmacro %}

{% macro snowflake__generate_pointer_alias(custom_alias_name, node) %}
    {{ (custom_alias_name or node.name) | upper }}
{% endmacro %}
```

## Macro que executa SQL diretamente (`statement` block)

Para operações que não retornam um `select` (ex.: `OPTIMIZE`, `GRANT`, `VACUUM`), use
`statement()` com `fetch_result=False` (ou `True` para capturar retorno).

```sql
-- macros/optimize_table.sql
{% macro optimize_table(table, zorder_fields=[]) %}
    {% set zorder_str = zorder_fields | join(', ') %}
    {% set query %}
        OPTIMIZE {{ table }}
        {% if zorder_str | length > 0 %}
        ZORDER BY ({{ zorder_str }})
        {% endif %}
    {% endset %}

    {% call statement('optimize', fetch_result=False) %}
        {{ query }}
    {% endcall %}
{% endmacro %}
```

Rodar via `run-operation` (fora do DAG de models):

```bash
dbt run-operation optimize_table --args '{table: "analytics.fct_orders", zorder_fields: ["order_date"]}'
```

## Estilo e legibilidade

```sql
{# BOM: espaçamento consistente, delimitadores claros #}
{% macro make_cool(uncool_id) %}

    do_cool_thing({{ uncool_id }})

{% endmacro %}
```

```sql
{# EVITAR: return() com operação algébrica inline — não suportado a partir do v2 parser #}
{% macro my_macro() %}
return('xyz') + 'abc'
{% endmacro %}

{# CORRETO: montar o valor antes de dar return #}
{% macro my_macro() %}
return('xyzabc')
{% endmacro %}
```

## dbt_utils — não reinvente antes de checar o package

Antes de escrever uma macro utilitária nova, verificar se `dbt-labs/dbt_utils` já cobre
o caso: `generate_surrogate_key`, `date_spine`, `pivot`, `star`, `union_relations`.

```yaml
# dependencies.yml
packages:
  - package: dbt-labs/dbt_utils
    version: 1.1.1
```

## Checklist

- [ ] Macro tem docstring/comentário explicando os argumentos, especialmente defaults
- [ ] Um arquivo por macro em `macros/` (ou agrupado por domínio em subpasta)
- [ ] Macro que roda SQL de efeito colateral (`statement()`) tem `fetch_result` explícito
- [ ] Antes de criar, checar se `dbt_utils` já resolve o caso
- [ ] `adapter.dispatch` usado só quando o comportamento realmente varia por warehouse —
      não adicionar indireção sem necessidade
