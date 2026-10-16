# Padrão: Testes Genéricos Reutilizáveis

## Quando usar

A mesma regra de qualidade se repete em múltiplos models/colunas (ex.: "todo CPF é
válido", "toda chave primária é positiva") — em vez de escrever um singular test por
ocorrência, escreva um generic test parametrizado uma vez.

## Anatomia de um generic test

```sql
-- macros/generic_tests/test_is_even.sql
{% test is_even(model, column_name) %}

with validation as (
    select {{ column_name }} as even_field
    from {{ model }}
),
validation_errors as (
    select even_field
    from validation
    where (even_field % 2) = 1   -- condição de FALHA — retorna linhas = teste falhou
)
select * from validation_errors

{% endtest %}
```

Uso — o parâmetro `model` é implícito, o resto vira argumento nomeado:

```yaml
models:
  - name: users
    columns:
      - name: favorite_number
        data_tests:
          - is_even:
              description: "favorite_number deve ser sempre par"
```

## Receita: test de faixa de valores (positivo, com limites)

```sql
-- macros/generic_tests/test_positive_value.sql
{% test positive_value(model, column_name, min_value=0) %}

select {{ column_name }}
from {{ model }}
where {{ column_name }} <= {{ min_value }}

{% endtest %}
```

```yaml
columns:
  - name: order_amount
    data_tests:
      - positive_value:
          arguments: {min_value: 0}
```

## Receita: test de formato (regex) — validar CPF/CNPJ sem expor dado raw

```sql
-- macros/generic_tests/test_valid_cpf_format.sql
{% test valid_cpf_format(model, column_name) %}

select {{ column_name }}
from {{ model }}
where {{ column_name }} is not null
  and not regexp_like({{ column_name }}, '^[0-9]{11}$')

{% endtest %}
```

## Composição: primary_key = unique + not_null num só nome

```sql
-- macros/generic_tests/test_primary_key.sql
{% test primary_key(model, column_name) %}

with dupes as (
    select {{ column_name }}, count(*) as n
    from {{ model }}
    group by 1
    having count(*) > 1 or {{ column_name }} is null
)
select * from dupes

{% endtest %}
```

```yaml
columns:
  - name: order_id
    data_tests:
      - primary_key
```

## Severidade e config por chamada

```yaml
data_tests:
  - positive_value:
      arguments: {min_value: 0}
      config:
        severity: warn        # não bloqueia o build, só loga
        where: "created_at > '2024-01-01'"   # aplica só a um subconjunto
```

Ou setar severidade default dentro do próprio macro do teste:

```sql
{% test positive_value(model, column_name, min_value=0) %}
{{ config(severity='warn') }}
...
{% endtest %}
```

## Organização recomendada

```
macros/
└── generic_tests/
    ├── test_is_even.sql
    ├── test_positive_value.sql
    ├── test_primary_key.sql
    └── test_valid_cpf_format.sql
```

Um arquivo por teste — facilita achar, revisar e versionar isoladamente.

## Checklist

- [ ] Nome do macro é `test_<nome>` mas a chamada em YAML usa só `<nome>` (sem prefixo)
- [ ] Teste tem caso de teste manual comprovando que ele FALHA quando deveria
- [ ] Argumentos com default sensato (`min_value=0`) para reduzir boilerplate no YAML
- [ ] Severidade declarada explicitamente quando não for `error` (default)
- [ ] Sem PII exposta no output do teste — retornar só a coluna testada, não a linha
      inteira, quando o campo é sensível
