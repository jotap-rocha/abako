# Sensor Pattern para Dependências Externas

## Quando este padrão se aplica

A DAG depende de um dado produzido **fora do controle do próprio Airflow**: arquivo chegando
num bucket de terceiro, resposta de uma API externa, tabela populada por outro sistema. Não é
o caso de asset scheduling (ver `concepts/asset-scheduling.md`), que é para dependências
entre DAGs do mesmo Airflow.

## Sensor deferrable + timeout + soft_fail — o template padrão

```python
from airflow.sdk import dag, task
from airflow.providers.amazon.aws.sensors.s3 import S3KeySensor
from pendulum import datetime

@dag(schedule="@daily", start_date=datetime(2026, 1, 1, tz="UTC"), catchup=False)
def ingest_partner_feed():

    wait_for_feed = S3KeySensor(
        task_id="wait_for_feed",
        bucket_name="partner-dropzone",
        bucket_key="feed/{{ ds }}/export.csv",
        deferrable=True,       # não ocupa worker slot durante a espera
        poke_interval=300,     # 5min entre checagens (usado no fallback não-deferred)
        timeout=60 * 60 * 8,   # 8h — janela máxima de espera do parceiro
        soft_fail=True,        # timeout vira "skipped", não "failed" — feed opcional
    )

    @task()
    def process_feed():
        ...

    wait_for_feed >> process_feed()

ingest_partner_feed()
```

## Sensor customizado — quando não existe provider pronto

```python
from airflow.sdk import BaseSensorOperator
from airflow.sensors.base import PokeReturnValue

class PartnerApiReadySensor(BaseSensorOperator):
    def __init__(self, *, endpoint: str, **kwargs):
        super().__init__(**kwargs)
        self.endpoint = endpoint

    def poke(self, context) -> bool | PokeReturnValue:
        status = check_partner_api(self.endpoint)
        if status == "ready":
            # PokeReturnValue permite passar dado direto pro XCom no momento do sucesso
            return PokeReturnValue(is_done=True, xcom_value={"status": status})
        return False
```

Para tornar deferrable, implemente `execute()` retornando um `Trigger` (async) em vez de
`poke()` — mais complexo, só compensa se a espera for longa E de alto volume (muitas DAG runs
esperando simultaneamente, onde o custo de N workers presos justifica o trigger assíncrono).

## Timeout do sensor vs timeout da DAG run

```python
@dag(
    schedule="@daily",
    start_date=...,
    dagrun_timeout=timedelta(hours=10),  # teto da RUN inteira, além do timeout do sensor
)
```

Declare os dois: `timeout` no sensor evita que uma task específica espere para sempre;
`dagrun_timeout` é o cinto de segurança da run completa (protege contra sensor + downstream
juntos ultrapassarem a janela operacional aceitável).

## Anti-padrão: sensor em `mode="poke"` sem timeout

```python
# ERRADO — trava um worker slot indefinidamente se o feed nunca chegar
wait = S3KeySensor(task_id="wait", bucket_key="...", mode="poke")
# sem timeout: se o parceiro nunca entregar, o slot fica preso para sempre,
# bloqueando outras DAGs que competem pelo mesmo pool
```

## Checklist

- [ ] `deferrable=True` quando o provider suporta (padrão para novas DAGs)
- [ ] `timeout` sempre declarado — nunca espera infinita
- [ ] `soft_fail=True` se a ausência do dado é um cenário de negócio válido
- [ ] `dagrun_timeout` no `@dag` como segunda camada de proteção
