---
domain: airflow
topic: quick-reference
---

# Airflow — Quick Reference

### Layout canônico

```
dags/
├── my_pipeline_dag.py       ← @dag + tasks via TaskFlow API
├── common/
│   ├── assets.py            ← definições de Asset compartilhadas
│   ├── operators/           ← operators customizados do projeto
│   └── sensors/             ← sensors customizados (deferrable)
├── config/
│   └── pools.yaml            ← definição de pools versionada (IaC)
└── tests/
    └── test_my_pipeline_dag.py  ← dag_bag.get_dag(...).test() ou unit test de task
```

### Invariantes

| # | Invariante |
|---|---|
| AF-01 | Toda task é idempotente — reexecutar com o mesmo `logical_date` não duplica dados (upsert, não insert puro) |
| AF-02 | Sem `datetime.now()`/estado mutável externo dentro da lógica da task — usar `logical_date`/`data_interval` do contexto |
| AF-03 | Sensor de longa espera usa `mode="reschedule"` ou `deferrable=True` — nunca `mode="poke"` ocupando worker por horas |
| AF-04 | XCom carrega apenas metadados pequenos (IDs, paths, contagens) — nunca DataFrames ou payloads grandes |
| AF-05 | Toda task com I/O externo declara `retries` + `retry_exponential_backoff=True` — sem retry infinito silencioso |
| AF-06 | Recursos compartilhados (DB, API rate-limited) usam `pool` dedicado — sem concorrência não controlada |
| AF-07 | Credenciais via Airflow Connections/Variables (ou secret backend) — nunca hardcoded na DAG |

### Decision tree: operator vs sensor vs asset scheduling

```
Preciso reagir à disponibilidade de um dado (não just rodar em horário fixo)?
    ├── SIM, e o dado é produzido por outra DAG do MEU Airflow
    │         → Asset scheduling: schedule=[meu_asset] (Airflow 3.x)
    ├── SIM, e o dado vem de sistema EXTERNO (S3, API, outro cluster)
    │         → Sensor deferrable (ex.: S3KeySensorAsync) com timeout
    └── NÃO, é so executar uma ação em horário fixo/cron
              → Operator normal + schedule="0 6 * * *" (cron) ou schedule="@daily"
```

### Comandos úteis

```bash
airflow dags test my_pipeline_dag 2026-07-26   # roda DAG local sem scheduler
airflow tasks test my_pipeline_dag extract 2026-07-26
airflow dags list-import-errors                # valida sintaxe de todas as DAGs
```
