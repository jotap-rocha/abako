# Dynamic Task Mapping

## O problema que resolve

O número de tasks necessárias só é conhecido em runtime (ex.: 1 task por arquivo encontrado,
1 task por cliente ativo naquele dia). Sem dynamic mapping, isso força DAGs estáticas com um
número fixo de tasks "reservadas", ou um loop Python gerando tasks no parse-time (que já é
conhecido de antemão, não dinâmico de fato).

## `expand()` — fan-out básico

```python
from airflow.sdk import dag, task
from pendulum import datetime

@dag(schedule="@daily", start_date=datetime(2026, 1, 1, tz="UTC"), catchup=False)
def process_partner_files():

    @task()
    def list_files() -> list[str]:
        return ["s3://drop/a.csv", "s3://drop/b.csv", "s3://drop/c.csv"]

    @task()
    def process_file(path: str) -> dict:
        row_count = load_and_process(path)
        return {"path": path, "row_count": row_count}

    # cria 1 task instance por item da lista — número decidido em runtime
    process_file.expand(path=list_files())

process_partner_files()
```

## `partial()` + `expand()` — argumentos fixos + argumentos mapeados

```python
@task()
def process_file(path: str, environment: str, chunk_size: int) -> dict:
    ...

process_file.partial(environment="prod", chunk_size=5000).expand(path=list_files())
# environment e chunk_size são iguais em todas as task instances;
# path varia por instance
```

## `expand_kwargs()` — múltiplos parâmetros combinados por item

```python
@task()
def sync_table(table: str, mode: str) -> None:
    ...

sync_table.expand_kwargs([
    {"table": "orders", "mode": "full"},
    {"table": "customers", "mode": "incremental"},
])
```

Use `expand_kwargs` quando os parâmetros mapeados **não são independentes entre si** (ex.: o
`mode` depende de qual `table` é) — `expand()` simples faria produto cartesiano se você
mapeasse dois argumentos separadamente.

## Agregando resultados do fan-out — o padrão map-reduce

```python
@task()
def summarize(results: list[dict]) -> None:
    total = sum(r["row_count"] for r in results)
    print(f"total processado: {total}")

processed = process_file.expand(path=list_files())
summarize(processed)  # TaskFlow injeta a lista completa de XComs mapeados
```

## Controlando concorrência do fan-out

```python
@task(max_active_tis_per_dag=10)   # no máximo 10 task instances mapeadas rodando em paralelo
def process_file(path: str) -> dict:
    ...
```

Sem esse limite, um `expand()` sobre 5.000 arquivos pode tentar disparar 5.000 task instances
simultâneas, saturando o executor/banco de metadados. Combine com `pools-priority.md` se o
gargalo for um recurso externo (não só o próprio Airflow).

## Gotchas

- `expand()` sobre uma lista vazia é válido — gera **zero** task instances, e a DAG segue sem
  erro (diferente de uma exceção). Trate explicitamente se "zero itens" for um cenário de
  alerta no seu domínio.
- Cada task instance mapeada é uma linha própria na UI/metadata — `expand()` sobre listas muito
  grandes (dezenas de milhares) degrada a UI e o scheduler; considere batelar (`chunk`) antes.
- XCom de retorno de uma task mapeada vira uma lista ao ser consumido — não assuma escalar.
