# Observabilidade de Pipeline

## O que é

Capacidade de entender o estado interno do pipeline a partir de seus outputs (logs, métricas, traces).
Responde: "está funcionando?", "onde parou?", "quantos registros foram perdidos?".

## Structured logging obrigatório

Use `structlog` (Python) para logs em JSON — parseável por Datadog, CloudWatch, Azure Monitor.

### Instalação

```bash
uv add structlog
```

### Setup

```python
import structlog

structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ]
)

log = structlog.get_logger()
```

### Campos obrigatórios por step

```python
log.info("pipeline_step_completed",
    # Identificação
    pipeline="orders_pipeline",
    layer="bronze",
    run_id=run_id,
    batch_id=batch_id,
    environment=config.environment,

    # Volume
    records_in=records_in,
    records_out=records_out,
    records_quarantined=records_quarantined,

    # Performance
    duration_ms=duration_ms,

    # Origem
    source=source_name,
    source_path=source_path,
)
```

**NUNCA incluir em logs:**
- PII (CPF, email, nome, dados financeiros, dados de saúde)
- Secrets ou tokens
- Dados de usuário não mascarados

### Log de anomalia

```python
quarantine_rate = records_quarantined / records_in * 100

if quarantine_rate > config.quarantine_rate_threshold_pct:
    log.warning("pipeline_anomaly",
        anomaly_type="high_quarantine_rate",
        rate_pct=round(quarantine_rate, 2),
        threshold_pct=config.quarantine_rate_threshold_pct,
        pipeline="orders_pipeline",
        layer="bronze",
        run_id=run_id,
    )
    notify_owner(config, anomaly_type="high_quarantine_rate", rate_pct=quarantine_rate)
```

### Log de falha

```python
try:
    result = run_bronze(spark, config, run_id)
except Exception as e:
    log.error("pipeline_step_failed",
        pipeline="orders_pipeline",
        layer="bronze",
        run_id=run_id,
        error_type=type(e).__name__,
        error_msg=str(e),
        # Não inclua stack trace completo — pode conter dados sensíveis
    )
    raise
```

## Métricas por camada

| Métrica | O que mede | Alerta quando |
|---|---|---|
| `records_in` | Registros recebidos da fonte | < baseline -20% |
| `records_out` | Registros escritos na camada | < records_in sem quarantine |
| `records_quarantined` | Registros em quarantine | > threshold (default 1%) |
| `duration_ms` | Tempo de execução do step | > p95 histórico |
| `null_rate_{campo}` | % de nulls em campo obrigatório | > 0.1% |
| `schema_mismatches` | Campos com tipo diferente do esperado | > 0 |

## Dashboards recomendados

Para Databricks com Unity Catalog:
- Databricks Monitoring → Job Runs → durations, failures
- Unity Catalog → Data Quality → expectations violations

Para on-premises:
- Grafana com Loki (logs) + Prometheus (métricas)
- Airflow UI → Task Logs, Duration, Gantt

## Checklist de observabilidade antes de ir a produção

- [ ] Structured logging implementado em todos os steps
- [ ] Campos obrigatórios presentes em cada log (pipeline, layer, run_id, records_*)
- [ ] Nenhum PII nos logs
- [ ] Alerta de quarantine rate configurado
- [ ] Alerta de falha configurado (Slack/Teams/email)
- [ ] Dashboard com histórico de runs configurado
- [ ] Threshold de quarantine rate definido no config/environments/prd.yaml
