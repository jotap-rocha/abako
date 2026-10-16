# Scheduling orientado a assets/datasets

## O conceito

Airflow 2.4 introduziu `Dataset` para scheduling data-aware: uma DAG dispara quando outra DAG
atualiza um dado do qual ela depende, em vez de depender só de cron. Airflow 3.0 renomeia e
expande esse modelo para **Assets** — um objeto de primeira classe que representa um dado
lógico (tabela, arquivo, tópico), com o `Assets` tab dedicado na UI e suporte a
`AssetAlias`/`AssetWatcher` para casos mais dinâmicos.

## Declarando e produzindo um asset

```python
from airflow.sdk import Asset, dag, task

orders_silver = Asset("s3://silver/orders/")

@dag(schedule="@daily", start_date=..., catchup=False)
def produce_orders_silver():
    @task(outlets=[orders_silver])
    def write_silver():
        ...  # grava o dado; o outlet marca o asset como atualizado ao final da task
    write_silver()
```

## Consumindo — schedule orientado a asset

```python
@dag(
    schedule=[orders_silver],   # dispara quando orders_silver é atualizado
    start_date=...,
    catchup=False,
)
def consume_orders_silver():
    @task()
    def aggregate():
        ...
    aggregate()
```

## Combinando múltiplos assets — AND lógico implícito

```python
schedule=[orders_silver, customers_silver]
```

A DAG só dispara quando **todos** os assets listados forem atualizados desde a última run
(cada um pelo menos uma vez). Para lógica mais fina (OR, janelas de tempo, condição custom),
use `AssetOr`/`AssetAnd` (Airflow 2.9+) ou uma `@asset`-based expression.

## `@asset` decorator (Airflow 3.x) — asset com lógica de produção acoplada

```python
from airflow.sdk import asset

@asset(schedule="@daily")
def orders_silver_asset(context):
    # a função É a lógica que produz o asset — Airflow cria a DAG implicitamente
    ...
```

Útil quando o asset tem exatamente um produtor — reduz boilerplate de declarar `Asset()` +
`@dag` + `outlets` separadamente.

## Quando usar asset scheduling vs cron

| Cenário | Escolha |
|---|---|
| Pipeline batch com hora fixa, sem dependência de outro pipeline | `schedule="0 6 * * *"` (cron) |
| DAG B só deve rodar depois que DAG A publica uma tabela | `schedule=[asset_da_tabela]` |
| Múltiplas DAGs downstream do mesmo dado (fan-out de consumo) | Asset — evita replicar cron em cada downstream e perder sincronia |
| Dependência externa fora do Airflow (S3 de terceiro, API) | Sensor (ver `sensors-vs-operators.md`), não asset |

## Gotchas

- Asset scheduling depende do **outlet ser executado com sucesso** — task que falha não
  atualiza o asset, então downstream não dispara (comportamento correto, mas confunde quem
  espera "rodou = atualizou").
- `AssetAlias` existe para casos onde o asset físico só é conhecido em runtime (ex.: path com
  data dinâmica) — declarar `Asset` estático quando o path muda por execução gera assets
  "fantasma" que nunca mais disparam.
- Asset scheduling não substitui `start_date`/backfill — combine com cuidado se o pipeline
  também precisa rodar em janela de tempo fixa.
