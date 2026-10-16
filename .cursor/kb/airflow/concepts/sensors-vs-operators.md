# Sensores vs Operators

## A diferença

**Operator** executa uma ação (roda um script, chama uma API, move um arquivo) e termina.
**Sensor** é um operator especializado que **espera até uma condição ser verdadeira** antes de
deixar a DAG prosseguir — ele "poka" (verifica) periodicamente até `poke_interval` ou até
`timeout`.

```python
from airflow.sdk import BaseSensorOperator

class MySensor(BaseSensorOperator):
    def poke(self, context) -> bool:
        return check_condition()  # True = condição satisfeita, libera downstream
```

## Os 3 modos de execução de um sensor

| Modo | Como funciona | Custo | Quando usar |
|---|---|---|---|
| `mode="poke"` | Ocupa 1 worker slot pelo tempo inteiro, checando a cada `poke_interval` | Alto — trava um slot por horas se a espera for longa | Espera curta (segundos/poucos minutos) |
| `mode="reschedule"` | Libera o worker slot entre checagens, reagenda a task | Médio — sem slot ocioso, mas ainda faz polling ativo | Espera de minutos a horas, sem suporte async |
| `deferrable=True` | Delega a espera ao **triggerer** (processo assíncrono dedicado), zero worker slot ocupado | Baixo — centenas de sensores deferred cabem num único triggerer | Padrão recomendado para qualquer espera > poucos minutos |

## Sensor deferrable — exemplo

```python
from airflow.providers.amazon.aws.sensors.s3 import S3KeySensor

wait_for_file = S3KeySensor(
    task_id="wait_for_file",
    bucket_name="raw-data",
    bucket_key="orders/{{ ds }}/orders.csv",
    deferrable=True,      # usa o triggerer, não bloqueia worker
    timeout=60 * 60 * 6,  # 6h — sempre declare timeout explícito
    mode="reschedule",    # fallback se o provider não suportar defer nativo
)
```

## `soft_fail` — sensor que falha vira "skipped", não "failed"

```python
wait_for_file = S3KeySensor(
    task_id="wait_for_file",
    ...,
    soft_fail=True,   # timeout → task state = skipped, não polui alertas de failure
)
```

Use quando a ausência do dado é um cenário esperado (ex.: feed opcional de fim de semana),
não uma falha real do pipeline.

## Quando usar Operator puro em vez de Sensor

Se a condição só precisa ser checada **uma vez** no início da task (não repetidamente até
ficar verdadeira), não é um sensor — é uma validação dentro de um operator/task normal que
levanta exceção se a pré-condição falhar. Sensor é para **esperar**, não para **validar**.

## Gotchas

- Sensor em `mode="poke"` sem timeout é a causa nº 1 de scheduler "travado" — todos os slots
  de um pool consumidos por sensores esperando indefinidamente.
- `deferrable=True` exige que o Airflow tenha um **triggerer** rodando (componente separado do
  scheduler) — sem ele, a task fica presa em `deferred` para sempre.
- Nem todo sensor tem versão deferrable nativa; verifique o provider antes de assumir suporte.
