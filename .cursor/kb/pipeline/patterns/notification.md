# Notificações de Anomalia no Pipeline

## Quando notificar

| Evento | Severidade | Canal |
|---|---|---|
| `schema_mismatch` | WARNING | Slack + Email |
| `high_quarantine_rate` | WARNING | Slack |
| `contract_violation` | ERROR | Slack + Email |
| `pipeline_step_failed` | ERROR | Slack + Email + PagerDuty (PRD) |
| `sla_breach` | WARNING | Slack + Email |
| `null_spike` | WARNING | Slack |

## Implementação base

```python
import httpx
import structlog
from config.pipeline_config import PipelineConfig

log = structlog.get_logger()

def notify_owner(
    config: PipelineConfig,
    anomaly_type: str,
    details: dict,
    run_id: str,
) -> None:
    """Envia notificação para owner do pipeline."""
    if not config.notifications_enabled:
        log.debug("notifications_disabled", anomaly_type=anomaly_type)
        return

    message = _build_message(config, anomaly_type, details, run_id)

    if config.slack_webhook_url:
        _send_slack(config.slack_webhook_url, message)

    if config.owner_email:
        _send_email(config.owner_email, anomaly_type, message)


def _build_message(
    config: PipelineConfig,
    anomaly_type: str,
    details: dict,
    run_id: str,
) -> str:
    emoji = ":warning:" if anomaly_type not in ("pipeline_step_failed",) else ":red_circle:"
    lines = [
        f"{emoji} *Pipeline Anomaly* — `{config.environment}`",
        f"*Type:* `{anomaly_type}`",
        f"*Run ID:* `{run_id}`",
    ]
    for k, v in details.items():
        lines.append(f"*{k}:* {v}")
    return "\n".join(lines)


def _send_slack(webhook_url: str, message: str) -> None:
    try:
        httpx.post(webhook_url, json={"text": message}, timeout=5)
    except Exception as e:
        log.error("slack_notification_failed", error=str(e))


def _send_email(email: str, subject: str, body: str) -> None:
    # Integre com seu sistema de email (SendGrid, SES, SMTP)
    # Exemplo com SMTP padrão:
    # import smtplib
    # from email.message import EmailMessage
    # msg = EmailMessage()
    # msg.set_content(body)
    # msg["Subject"] = f"[Pipeline Alert] {subject}"
    # msg["From"] = "pipeline-alerts@company.com"
    # msg["To"] = email
    # ...
    log.info("email_notification_placeholder", to=email, subject=subject)
```

## Uso no pipeline

```python
# Schema mismatch detectado:
notify_owner(
    config,
    anomaly_type="schema_mismatch",
    details={
        "pipeline": "orders_pipeline",
        "layer": "bronze",
        "expected_fields": "order_id, amount, created_at",
        "missing_fields": "created_at",
        "records_affected": invalid_df.count(),
        "quarantine_table": config.quarantine_table(),
    },
    run_id=run_id,
)

# Taxa de quarantine acima do threshold:
notify_owner(
    config,
    anomaly_type="high_quarantine_rate",
    details={
        "rate_pct": round(quarantine_rate, 2),
        "threshold_pct": config.quarantine_rate_threshold_pct,
        "pipeline": "orders_pipeline",
        "records_quarantined": records_quarantined,
        "records_in": records_in,
    },
    run_id=run_id,
)
```

## Configuração por ambiente

```yaml
# config/environments/local.yaml
notifications_enabled: false   # nunca notifica em local

# config/environments/dev.yaml
notifications_enabled: true
owner_email: "data-team@company.com"
slack_webhook_url: "https://hooks.slack.com/services/..."

# config/environments/prd.yaml
notifications_enabled: true
owner_email: "data-team@company.com"
slack_webhook_url: "https://hooks.slack.com/services/..."
```
