# Fusion Engine

## O que é

Fusion é o novo engine de compilação/execução do dbt (dbt Core v2.0, pré-release em
2026), reescrito em Rust. Substitui o parser Python + Jinja tradicional por um parser e
analisador SQL nativos, com foco em velocidade e correção estática antes de qualquer
query rodar no warehouse.

## Diferenças-chave vs dbt Core clássico

| Aspecto | dbt Core clássico | Fusion |
|---|---|---|
| Parser | Python + Jinja | Rust, parser SQL nativo (v2 parser) |
| Validação | Em runtime, contra o warehouse | Análise estática antes de executar |
| Erros de coluna/tipo | Descobertos ao rodar a query | Detectados na compilação |
| Instalação | `pip install dbt-core` | `pip install --pre dbt` (ainda pré-release) |

## Static analysis

Fusion analisa o SQL estaticamente (sem rodar no warehouse) para pegar erros de
referência de coluna, tipo e sintaxe antes do `dbt run`. Tem 3 modos configuráveis por
model — útil quando o SQL usa UDF/funções que a análise estática não reconhece.

```sql
{{ config(static_analysis='strict' | 'baseline' | 'off') }}
```

```sql
-- desabilitar quando o model usa UDF custom não suportada pela análise estática
{{ config(static_analysis='off') }}
select user_id, my_cool_udf(ip_address) as cleaned_ip
from {{ ref('my_model') }}
```

Pode ser setado por diretório também:

```yaml
# dbt_project.yml
models:
  [resource-path]:
    +static_analysis: strict | baseline | off
```

## v2 parser (opt-in em dbt Core clássico)

O parser Rust do Fusion pode ser habilitado dentro do dbt Core clássico como preview,
antes de migrar totalmente para Fusion:

```yaml
# dbt_project.yml
flags:
  use_v2_parser: true
```

## Instalação e verificação

```bash
python -m pip install --pre dbt
dbt --version
# dbt 2.0.0-preview.178
```

## Estado atual (limitações conhecidas)

Fusion ainda está em pré-GA (General Availability) — antes de migrar um projeto,
verificar a lista de features não suportadas na doc oficial `fusion/supported-features`.
Riscos conhecidos:

- Materializations com features avançadas específicas de adapter podem não rodar ou
  perder configurações.
- Log output difere do dbt Core clássico — tooling que faz parsing de log pode quebrar.
- Notificações a nível de model (features complementares da plataforma) ainda não têm
  suporte completo.
- `require-dbt-version` no `dbt_project.yml`/packages precisa declarar compatibilidade
  explícita com `>=2.0.0` para funcionar em Fusion.

## Quando considerar Fusion hoje

```
O projeto está em produção crítica, com adapters/packages não testados em Fusion?
    └── Ficar no dbt Core clássico até GA — Fusion ainda é pré-release

O projeto é novo, pequeno, ou dá para rodar side-by-side (dbtf compile) para validar?
    └── Testar Fusion em paralelo — ganho de performance de compilação é real,
        mas validar com `dbt retry`/`dbt run --select` antes de trocar de vez
```

## Gotchas

- `--no-partial-parse` está deprecated em Fusion — não usar essa flag, o parsing
  incremental é tratado de forma diferente internamente.
- Funções de ML/warehouse (ex.: Snowflake `!predict`) retornam `VARIANT` sob Fusion —
  fazer cast explícito (`::float`) onde o dbt Core clássico inferia o tipo automaticamente.
- Fusion não é drop-in replacement silencioso — rodar `dbt build --select` num subconjunto
  de models antes de migrar o projeto inteiro.
