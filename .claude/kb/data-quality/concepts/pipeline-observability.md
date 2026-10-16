---
topic: pipeline-observability
confidence: null
mcp_validated: null
---

# Observabilidade de Pipeline — Freshness, Volume, Schema Drift

> Ver também: `pipeline/concepts/observability.md` — cobre a implementação (structured logging,
> `structlog`, dashboards). Este arquivo cobre o **o quê monitorar** em nível de dado
> (data observability), independente de qual ferramenta de logging é usada por baixo.

## Os 3 pilares centrais

Framework comum a ferramentas de data observability (Monte Carlo, Soda, dbt): todo pipeline
deveria ter alerta automático para estes 3 sinais, mesmo sem nenhuma ferramenta de mercado —
são queries simples de metadado.

| Pilar | Pergunta | Sinal de anomalia |
|---|---|---|
| **Freshness** | O dado está atualizado o suficiente? | `max(_ingested_at)` mais antigo que o SLA |
| **Volume** | A quantidade de dados está dentro do esperado? | Contagem de linhas fora do range histórico |
| **Schema drift** | O schema mudou sem aviso? | Coluna nova/removida/tipo mudou vs baseline |

## Freshness

```sql
SELECT
  table_name,
  max(_ingested_at) AS last_load,
  datediff(hour, max(_ingested_at), current_timestamp()) AS hours_stale
FROM orders_silver
GROUP BY table_name
HAVING hours_stale > 24;  -- SLA do contrato
```

`dbt source freshness` automatiza esse check por source declarado em `sources.yml`
(ver `patterns/dbt-tests.md`).

## Volume

Detecção de anomalia por comparação com baseline histórico (não threshold fixo — volume varia
por dia da semana, sazonalidade).

```sql
WITH daily_counts AS (
  SELECT date(_ingested_at) AS load_date, count(*) AS row_count
  FROM orders_silver
  WHERE _ingested_at >= current_date() - interval 30 days
  GROUP BY date(_ingested_at)
),
stats AS (
  SELECT avg(row_count) AS avg_count, stddev(row_count) AS stddev_count
  FROM daily_counts
  WHERE load_date < current_date()
)
SELECT d.load_date, d.row_count, s.avg_count,
       (d.row_count - s.avg_count) / nullif(s.stddev_count, 0) AS z_score
FROM daily_counts d, stats s
WHERE d.load_date = current_date()
  AND abs((d.row_count - s.avg_count) / nullif(s.stddev_count, 0)) > 3;  -- 3 desvios-padrão
```

Regra prática: alerta quando volume do dia foge `> 3 stddev` da média móvel de 30 dias — evita
falso positivo em picos sazonais conhecidos (ex.: Black Friday precisa de baseline separado).

## Schema drift

```python
# Compara schema atual vs baseline salvo (ex.: schema declarado no contrato ODCS)
def detect_schema_drift(current_schema: dict, baseline_schema: dict) -> dict:
    added = set(current_schema) - set(baseline_schema)
    removed = set(baseline_schema) - set(current_schema)
    type_changed = {
        field for field in set(current_schema) & set(baseline_schema)
        if current_schema[field] != baseline_schema[field]
    }
    return {"added": added, "removed": removed, "type_changed": type_changed}
```

Classifique o drift antes de agir — nem toda mudança de schema é breaking
(ver `concepts/data-contracts-odcs.md` → `lifecycle`):

| Drift | Classificação | Ação |
|---|---|---|
| Coluna nova, nullable | não-breaking | log + segue |
| Coluna removida | breaking | quarantine + notify (ver `patterns/quarantine-notification.md`) |
| Tipo mudou (ex.: string→int) | breaking | quarantine + notify |

## Como isso difere de "observabilidade de aplicação"

Observabilidade de app mede latência/erro de request. Observabilidade de *dado* mede se o
**conteúdo** está certo — um pipeline pode rodar 100% verde (sem exceção) e ainda entregar dado
errado (freshness estourada, volume caiu pela metade, schema mudou). Os checks aqui não
aparecem em APM tradicional — precisam de instrumentação própria ou ferramenta dedicada
(Soda, Monte Carlo, `dbt source freshness`).

## Gotchas

- **Threshold fixo de volume gera alert fatigue** — prefira desvio-padrão sobre baseline móvel a
  número fixo "sempre entre 900k e 1.1M linhas".
- **Freshness mede a *carga*, não o *evento*** — `_ingested_at` recente não garante que o dado de
  origem também é recente; se a fonte está atrasada, meça `event_time` separadamente.
- **Schema drift silencioso é o pior caso** — se a ferramenta só loga e não bloqueia campo
  removido, o consumidor a jusante quebra sem aviso. Drift breaking deve ir para quarantine.
