# DAG Idempotente com Retry/Backoff

## O princípio

Uma DAG idempotente pode ser reexecutada (retry automático, backfill, replay manual) para o
mesmo `logical_date`/`data_interval` **infinitas vezes** e produzir sempre o mesmo estado final
— nunca duplica linhas, nunca soma valores duas vezes.

## Particionar por `logical_date`, nunca por "agora"

```python
from airflow.sdk import dag, task
from pendulum import datetime

@dag(
    dag_id="orders_idempotent",
    schedule="@daily",
    start_date=datetime(2026, 1, 1, tz="UTC"),
    catchup=False,
    default_args={
        "retries": 4,
        "retry_delay": 60,                  # segundos, delay inicial
        "retry_exponential_backoff": True,  # 60s, 120s, 240s, 480s...
        "max_retry_delay": 900,             # teto de 15min entre tentativas
    },
)
def orders_idempotent():

    @task()
    def extract(**context) -> str:
        # ERRADO: usar datetime.now() — cada retry pegaria uma janela diferente
        # CERTO: usar o data_interval do contexto da run
        data_interval_start = context["data_interval_start"]
        partition = data_interval_start.format("YYYY-MM-DD")
        return f"s3://raw/orders/{partition}/"

    @task()
    def load(raw_path: str, **context) -> None:
        partition = context["data_interval_start"].format("YYYY-MM-DD")
        # UPSERT/MERGE por partição — não INSERT puro
        run_merge(target="orders_silver", partition=partition, source=raw_path)

    load(extract())

orders_idempotent()
```

## MERGE/upsert em vez de INSERT — a técnica central

```python
def run_merge(target: str, partition: str, source: str) -> None:
    # Delete-then-insert da partição inteira (simples, funciona bem para batch diário)
    execute_sql(f"""
        DELETE FROM {target} WHERE partition_date = '{partition}';
        INSERT INTO {target}
        SELECT * FROM read_source('{source}');
    """)
    # Alternativa: MERGE/UPSERT por chave de negócio se a granularidade
    # exigir merge dentro da própria partição
```

## Retry com backoff exponencial — parâmetros

| Parâmetro | Efeito |
|---|---|
| `retries` | Nº de novas tentativas após a primeira falha (não conta a execução original) |
| `retry_delay` | Delay antes da 1ª retry |
| `retry_exponential_backoff=True` | Cada retry dobra o delay anterior (com jitter) |
| `max_retry_delay` | Teto — evita que o backoff cresça sem limite em falhas persistentes |

## Falhas transitórias vs falhas de dado

```python
@task(retries=5, retry_exponential_backoff=True)
def call_external_api(**context):
    try:
        return fetch_from_api()
    except TransientNetworkError:
        raise  # deixa o Airflow reter — é o cenário que retry resolve
    except InvalidPayloadError:
        # dado ruim não se resolve com retry — falha definitiva, sem retry
        raise AirflowFailException("payload inválido, não retentar")
```

`AirflowFailException` marca a task como `failed` **sem consumir os retries restantes** —
use para erros que retry não vai corrigir.

## Checklist de idempotência

- [ ] Nenhuma chamada a `datetime.now()`/`uuid.uuid4()` dentro da lógica de negócio da task
- [ ] Toda escrita em storage/DB é upsert, merge ou delete+insert por partição
- [ ] `retries` + `retry_exponential_backoff=True` declarados em toda task com I/O externo
- [ ] Erros de dado (não transitórios) usam `AirflowFailException`, não deixam retry rodar em vão
- [ ] `max_active_runs` limitado se a mesma partição pode ser processada por runs concorrentes
