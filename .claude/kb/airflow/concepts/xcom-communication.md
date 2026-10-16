# XComs e comunicação entre tasks

## O que é XCom

XCom ("cross-communication") é o mecanismo do Airflow para uma task passar dados para outra.
Por padrão, XComs são serializados (JSON) e gravados na tabela `xcom` do metadata DB —
**não** foi projetado para payloads grandes.

## TaskFlow API — XCom automático

```python
@task()
def extract() -> dict:
    return {"path": "s3://raw/orders/2026-07-26/", "row_count": 4210}
    # o retorno vira um XCom push automático

@task()
def report(extract_result: dict) -> None:
    print(f"{extract_result['row_count']} linhas em {extract_result['path']}")

extract_result = extract()
report(extract_result)  # XCom pull automático — sem xcom_pull manual
```

## `multiple_outputs` — múltiplos XComs nomeados a partir de um dict

```python
@task(multiple_outputs=True)
def extract() -> dict:
    return {"path": "s3://raw/orders/", "row_count": 4210}
    # cria 2 XComs separados: "path" e "row_count", visíveis individualmente na UI
```

## API manual (fora do TaskFlow, ex.: dentro de um operator custom)

```python
def my_callable(**context):
    context["ti"].xcom_push(key="row_count", value=4210)

def downstream_callable(**context):
    row_count = context["ti"].xcom_pull(task_ids="extract", key="row_count")
```

## O que NUNCA colocar em um XCom

| Não faça | Faça em vez disso |
|---|---|
| Retornar um DataFrame/lista de milhões de linhas | Gravar em storage (S3/GCS/tabela) e retornar o **path/URI** |
| Retornar credenciais ou PII | Usar Connections/Variables/secret backend; nunca dado sensível trafegando pelo metadata DB |
| Depender de XCom para estado entre DAG runs diferentes | XCom é escopado à run — usar Variable ou o próprio dado persistido para estado entre runs |

## Custom XCom backend — quando o payload precisa ser maior

Para objetos que legitimamente precisam trafegar entre tasks (não apenas referências), configure
um **custom XCom backend** (ex.: gravar em S3, XCom só guarda a chave):

```python
# airflow.cfg ou env var
AIRFLOW__CORE__XCOM_BACKEND = "my_project.xcom_backends.S3XComBackend"
```

Isso troca o backend padrão (Postgres) por armazenamento externo, mantendo a mesma API
`xcom_push`/`xcom_pull`/retorno de `@task`.

## Gotchas

- XCom no metadata DB tem limite prático por engine (ex.: Postgres `~1GB` por linha, mas
  performance degrada muito antes disso) — trate como "poucos KB", não como storage de dados.
- `ti.xcom_pull()` sem `task_ids` traz o XCom da **última task upstream que fez push com essa
  key** — em DAGs com múltiplos upstreams, sempre especifique `task_ids` explicitamente.
- XComs de tasks mapeadas dinamicamente (`expand()`) retornam uma lista — iterar exige
  `.map()`/list comprehension, não acesso direto por índice fixo se a quantidade for dinâmica.
