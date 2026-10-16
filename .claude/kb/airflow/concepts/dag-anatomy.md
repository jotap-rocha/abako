# Anatomia de uma DAG (TaskFlow API)

## O que é a TaskFlow API

Desde Airflow 2.0 (e consolidada em 3.x), a TaskFlow API substitui a construção manual de
`PythonOperator` + `set_downstream` por decorators (`@dag`, `@task`). Dependências entre tasks
são inferidas automaticamente pelo fluxo de dados (quem chama quem), não declaradas à mão.

## Estrutura mínima

```python
from airflow.sdk import dag, task
# Airflow 3.x: decorators e context vêm de airflow.sdk (Task Execution API / Task SDK)
# Em bases 2.x, o import equivalente é airflow.decorators

from pendulum import datetime

@dag(
    dag_id="orders_daily_pipeline",
    schedule="@daily",
    start_date=datetime(2026, 1, 1, tz="UTC"),
    catchup=False,
    default_args={
        "retries": 3,
        "retry_delay": 300,  # segundos
        "retry_exponential_backoff": True,
    },
    tags=["orders", "medallion-bronze"],
)
def orders_daily_pipeline():

    @task()
    def extract() -> str:
        # retorna um path/URI — não o dado em si (ver xcom-communication.md)
        return "s3://raw/orders/2026-07-26/"

    @task()
    def transform(raw_path: str) -> str:
        return raw_path.replace("raw", "silver")

    @task()
    def load(silver_path: str) -> None:
        print(f"loading {silver_path}")

    # dependência inferida pelo encadeamento de chamadas — sem >> explícito
    raw_path = extract()
    silver_path = transform(raw_path)
    load(silver_path)

orders_daily_pipeline()
```

## Por que preferir TaskFlow a operators manuais

| TaskFlow API | Operators manuais (`PythonOperator`) |
|---|---|
| Dependência inferida pelo retorno da função | `>>` explícito, fácil esquecer/errar |
| XCom automático (retorno = push) | `xcom_push`/`xcom_pull` manual |
| Type hints validam o contrato entre tasks | Sem contrato — `dict` genérico |
| Testável como função Python pura | Precisa instanciar operator + contexto |

## Parâmetros do `@dag` que todo pipeline deve declarar

- `schedule`: cron, preset (`@daily`) ou lista de assets (ver `asset-scheduling.md`)
- `start_date`: fixo, nunca `datetime.now()` — quebra idempotência do scheduler
- `catchup`: `False` por padrão, salvo backfill intencional
- `default_args.retries` + `retry_exponential_backoff`: todo pipeline de produção tem retry
- `max_active_runs`: limita runs concorrentes da mesma DAG (evita corrida em recursos)

## Task groups — organização visual sem afetar execução

```python
from airflow.sdk import task_group

@task_group(group_id="bronze_to_silver")
def bronze_to_silver():
    t1 = clean_nulls()
    t2 = dedupe(t1)
    return t2
```

`@task_group` é só namespacing/visualização na UI — não muda scheduling nem XCom.

## Gotchas

- **Top-level code roda a cada parse do scheduler** (a cada `min_file_process_interval`,
  default 30s). Nunca faça chamadas de rede, leitura de DB ou I/O pesado fora de uma `@task` —
  isso trava o DAG parsing e degrada o scheduler inteiro.
- `start_date` no passado + `catchup=True` sem querer = backfill descontrolado consumindo
  todos os slots do pool.
- Import de `airflow.sdk` (Task SDK) é a forma recomendada no Airflow 3.x para código que roda
  dentro da task (isolamento entre scheduler e worker); imports diretos de `airflow.models`
  dentro da lógica de task acoplam ao runtime do scheduler.
