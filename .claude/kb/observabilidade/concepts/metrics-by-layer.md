# Métricas por Camada

## Framework de métricas para agentes LLM

```
Latência total (p50 / p95 / p99)
├── classify_node
├── search_node (Qdrant)
├── run_sql_node (Postgres)
└── generate_node (LLM)

Custo
├── tokens de entrada (LLM)
├── tokens de saída (LLM)
└── embedding calls

Qualidade
├── grounding_rate      (% respostas com fonte citada)
├── relevance_score     (avaliação humana ou LLM-as-judge)
└── answer_rate         (% queries que receberam resposta vs recusa)

Erros
├── error_rate          (% runs com erro)
├── timeout_rate        (% queries que excederam timeout)
└── hallucination_flag  (detectado via avaliação)
```

## Coleta de métricas (Python)

```python
import time
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class RunMetrics:
    session_id: str
    query: str
    intent: str = ""
    classify_ms: float = 0
    search_ms: float = 0
    sql_ms: float = 0
    generate_ms: float = 0
    total_ms: float = 0
    input_tokens: int = 0
    output_tokens: int = 0
    sources_count: int = 0
    has_grounding: bool = False
    error: Optional[str] = None

    @property
    def estimated_cost_usd(self) -> float:
        # gpt-4o: $2.50/1M input, $10/1M output
        return (self.input_tokens / 1_000_000 * 2.50 +
                self.output_tokens / 1_000_000 * 10.0)

class MetricsCollector:
    def __init__(self, langfuse, db_pool):
        self.langfuse = langfuse
        self.db = db_pool

    async def record(self, metrics: RunMetrics, trace_id: str):
        # Gravar no harness (schema local)
        async with self.db.acquire() as conn:
            await conn.execute("""
                INSERT INTO harness.runs
                  (session_id, intent, total_ms, input_tokens, output_tokens,
                   has_grounding, sources_count, error, created_at)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8, now())
            """, metrics.session_id, metrics.intent, metrics.total_ms,
                metrics.input_tokens, metrics.output_tokens,
                metrics.has_grounding, metrics.sources_count, metrics.error)

        # Score de grounding no Langfuse
        self.langfuse.score(
            trace_id=trace_id,
            name="grounding",
            value=1.0 if metrics.has_grounding else 0.0,
        )
```

## SLOs (Service Level Objectives)

| Métrica | Target | Alerta |
|---|---|---|
| Latência p95 | < 8s | > 10s |
| Latência p99 | < 15s | > 20s |
| Error rate | < 2% | > 5% |
| Grounding rate | > 90% | < 80% |
| Custo/dia | < $X | > $X * 1.5 |
| Answer rate | > 85% | < 75% |

## Query de análise (Postgres)

```sql
-- Latência por nó nos últimos 7 dias
SELECT
  date_trunc('day', created_at) AS dia,
  intent,
  round(avg(total_ms)) AS avg_ms,
  round(percentile_cont(0.95) WITHIN GROUP (ORDER BY total_ms)) AS p95_ms,
  count(*) AS runs,
  round(avg(CASE WHEN error IS NULL THEN 1 ELSE 0 END) * 100, 1) AS success_rate,
  round(avg(CASE WHEN has_grounding THEN 1 ELSE 0 END) * 100, 1) AS grounding_rate
FROM harness.runs
WHERE created_at > now() - interval '7 days'
GROUP BY 1, 2
ORDER BY 1 DESC, 3 DESC;

-- Custo estimado por dia
SELECT
  date_trunc('day', created_at) AS dia,
  sum(input_tokens) AS total_input_tokens,
  sum(output_tokens) AS total_output_tokens,
  round((sum(input_tokens) / 1e6 * 2.50 + sum(output_tokens) / 1e6 * 10.0)::numeric, 4) AS custo_usd
FROM harness.runs
GROUP BY 1
ORDER BY 1 DESC;
```

## Dashboard mínimo (/scorecard)

```
=== SCORECARD — últimas 24h ===

Latência    p50: 2.1s   p95: 7.8s   p99: 12.3s
Qualidade   grounding: 94%   answer_rate: 88%
Custo       $0.82/dia   ($0.024 avg/run)
Erros       error_rate: 1.2%   timeout: 0.3%
Volume      342 runs

Alertas: NENHUM
```
