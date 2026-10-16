# Thresholds de Alerta

## Tabela de referência

| Métrica | Nível Normal | Warning | Critical | Ação |
|---|---|---|---|---|
| Latência p95 | < 5s | 5–10s | > 10s | Investigar nó mais lento |
| Latência p99 | < 10s | 10–20s | > 20s | Checar timeout de LLM/DB |
| Error rate | < 1% | 1–5% | > 5% | Checar logs de erro |
| Grounding rate | > 95% | 85–95% | < 85% | Revisar prompts e fontes |
| Answer rate | > 90% | 80–90% | < 80% | Revisar intent classifier |
| Custo/dia | baseline | > 150% | > 200% | Checar uso inesperado |
| DB query p95 | < 500ms | 500ms–2s | > 2s | Verificar índices/LIMIT |
| Qdrant search p95 | < 200ms | 200–500ms | > 500ms | Verificar payload indexes |

## Verificação automática no /scorecard

```python
from dataclasses import dataclass

@dataclass
class SLOCheck:
    name: str
    value: float
    warning: float
    critical: float
    higher_is_better: bool = False  # True para grounding_rate, answer_rate

    @property
    def status(self) -> str:
        if self.higher_is_better:
            if self.value >= self.warning: return "OK"
            if self.value >= self.critical: return "WARNING"
            return "CRITICAL"
        else:
            if self.value <= self.warning: return "OK"
            if self.value <= self.critical: return "WARNING"
            return "CRITICAL"

async def check_slos(db_pool) -> list[SLOCheck]:
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT
              percentile_cont(0.95) WITHIN GROUP (ORDER BY total_ms) AS p95_ms,
              avg(CASE WHEN error IS NOT NULL THEN 1.0 ELSE 0.0 END) * 100 AS error_rate,
              avg(CASE WHEN has_grounding THEN 1.0 ELSE 0.0 END) * 100 AS grounding_rate
            FROM harness.runs
            WHERE created_at > now() - interval '1 hour'
        """)

    return [
        SLOCheck("latencia_p95_ms", row["p95_ms"] or 0, warning=5000, critical=10000),
        SLOCheck("error_rate_%", row["error_rate"] or 0, warning=1.0, critical=5.0),
        SLOCheck("grounding_rate_%", row["grounding_rate"] or 100,
                 warning=95.0, critical=85.0, higher_is_better=True),
    ]
```

## Alerta via Slack/webhook

```python
import httpx

async def send_alert(webhook_url: str, checks: list[SLOCheck]):
    critical = [c for c in checks if c.status == "CRITICAL"]
    warnings = [c for c in checks if c.status == "WARNING"]

    if not critical and not warnings:
        return  # sem alerta

    emoji = "🚨" if critical else "⚠️"
    lines = [f"{emoji} *Alerta de Observabilidade* — {datetime.now().strftime('%Y-%m-%d %H:%M')}"]

    for c in critical:
        lines.append(f"🔴 CRITICAL `{c.name}`: {c.value:.1f} (limite: {c.critical})")
    for w in warnings:
        lines.append(f"🟡 WARNING `{w.name}`: {w.value:.1f} (limite: {w.warning})")

    async with httpx.AsyncClient() as client:
        await client.post(webhook_url, json={"text": "\n".join(lines)})
```

## Integração no /scorecard

```python
# .claude/commands/scorecard.md invoca:
async def run_scorecard():
    checks = await check_slos(db_pool)
    has_critical = any(c.status == "CRITICAL" for c in checks)

    print("=== SCORECARD ===")
    for c in checks:
        icon = {"OK": "✅", "WARNING": "⚠️", "CRITICAL": "🔴"}[c.status]
        print(f"{icon} {c.name}: {c.value:.1f}")

    if has_critical:
        await send_alert(SLACK_WEBHOOK, checks)

    return checks
```

## Limites por tipo de projeto

| Tipo | Latência p95 alvo | Custo alvo/dia |
|---|---|---|
| Chatbot interno | < 10s | < $5 |
| API de produção pública | < 5s | definir por volume |
| Análise em batch | < 60s | custo por job |
| RAG de docs | < 8s | < $2 |
