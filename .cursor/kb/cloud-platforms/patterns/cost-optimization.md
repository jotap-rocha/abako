# Otimização de Custo — Snowflake, Databricks, BigQuery

Padrões de redução de custo aplicáveis por plataforma. A alavanca comum às três: **reduzir bytes
processados/scanneados** e **reduzir tempo de compute ocioso**.

## Auto-suspend / autotermination — matar compute ocioso

### Snowflake — `AUTO_SUSPEND`

```sql
CREATE WAREHOUSE analytics_wh
  WAREHOUSE_SIZE = 'MEDIUM'
  AUTO_SUSPEND = 60          -- suspende após 60s sem query
  AUTO_RESUME = TRUE;        -- resume automaticamente na próxima query
```
Regra prática: warehouses interativos (BI, ad-hoc) → `AUTO_SUSPEND` curto (60-300s). Warehouses
de ETL batch → pode ser maior se o pipeline roda queries em sequência contínua (evita
resume/suspend repetido que gasta crédito de startup).

### Databricks — `autotermination_minutes`

```python
cluster_config = {
    "autotermination_minutes": 30,   # cluster interativo desliga após 30min ocioso
    "autoscale": {"min_workers": 1, "max_workers": 8},
}
```
Jobs Compute (cluster efêmero criado só para o job, destruído ao fim) é sempre mais barato que
All-Purpose Compute deixado ligado — separar workload de produção agendada de exploração
interativa é a alavanca de custo nº 1 em Databricks.

### BigQuery — não há "cluster" para suspender (serverless)

Em BigQuery o equivalente é: usar **on-demand** para cargas irregulares em vez de reservar slots
fixos que ficam ociosos fora de horário de pico, ou usar **autoscaling de reservations** (BigQuery
Editions) para escalar slots para baixo automaticamente em baixa demanda.

## Right-sizing — não superdimensionar compute

| Plataforma | Sintoma de over-provisioning | Ação |
|---|---|---|
| Snowflake | Query M/L não acelera vs S/M (poucos micro-partitions) | Reduzir warehouse size, medir tempo antes/depois |
| Databricks | Autoscaling nunca atinge `max_workers`, custo alto por ocioso nos workers extras | Reduzir `max_workers`, revisar `min_workers=0` se workload é intermitente |
| BigQuery | Slots reservados com baixa utilização média (< 60%) | Reduzir edition/commitment, migrar parte da carga para on-demand |

Regra prática comum: comece pequeno, meça, escale sob medida — nunca dimensione "para o pior
caso hipotético" sem dados de uso real.

```sql
-- Snowflake: medir uso de warehouse para right-sizing
SELECT warehouse_name, warehouse_size,
       AVG(execution_time)/1000 AS avg_exec_sec,
       COUNT(*) AS query_count
FROM snowflake.account_usage.query_history
WHERE start_time > DATEADD(day, -30, CURRENT_TIMESTAMP())
GROUP BY 1, 2
ORDER BY query_count DESC;
```

## Particionamento e clustering — reduzir bytes escaneados

### BigQuery — partition + cluster

```sql
CREATE TABLE analytics.orders
PARTITION BY DATE(created_at)      -- reduz scan por range de data
CLUSTER BY customer_id, status     -- reduz scan dentro da partição
AS SELECT * FROM staging.orders;

-- Query correta: filtra a coluna de partição explicitamente
SELECT * FROM analytics.orders
WHERE DATE(created_at) = '2026-07-01'   -- só escaneia 1 partição
  AND customer_id = 4521;
```
Sem filtro na coluna de partição, o BigQuery escaneia a tabela inteira mesmo com partition
configurada — o otimizador não infere a partição, precisa do filtro explícito.

### Snowflake — clustering key (micro-partition pruning)

```sql
ALTER TABLE analytics.orders CLUSTER BY (created_at, customer_id);
```
Snowflake já faz pruning automático via metadados de micro-partition; clustering key manual só
compensa em tabelas muito grandes (> centenas de GB) com padrão de filtro consistente — validar
com `SYSTEM$CLUSTERING_INFORMATION` antes de aplicar, o custo de manter o clustering (background
re-clustering) também consome crédito.

### Databricks — partition + Z-ORDER / liquid clustering

```python
# Delta Lake: particionar por coluna de baixa cardinalidade
df.write.partitionBy("event_date").format("delta").save(path)

# Z-ORDER: co-localizar dados por colunas de filtro frequente (alta cardinalidade)
spark.sql("OPTIMIZE analytics.orders ZORDER BY (customer_id)")

# Liquid clustering (Delta Lake moderno): substitui partition+Z-ORDER,
# reclustera incrementalmente sem precisar reescrever a tabela inteira
spark.sql("ALTER TABLE analytics.orders CLUSTER BY (customer_id, status)")
```

## Checklist rápido de otimização (aplica-se às três)

1. Auto-suspend/autotermination configurado em todo compute interativo — nunca deixar default
   "sempre ligado".
2. Separar compute de produção (batch/jobs, previsível) de compute exploratório (interativo,
   variável) — evita que exploração ad-hoc infle a fatura de produção.
3. Medir antes de redimensionar — right-sizing sem dado de uso real é chute caro.
4. Toda tabela grande (> dezenas de GB) tem estratégia de partição/clustering definida e
   documentada — não deixar "crescer organicamente" sem revisão.
5. Revisar mensalmente queries de maior custo (`account_usage` no Snowflake, `system.billing` no
   Databricks, `INFORMATION_SCHEMA.JOBS` no BigQuery) — os 20% de queries mais caras geralmente
   respondem por 80% do custo evitável.

## Gotchas

- Auto-suspend muito agressivo (ex: 10s) em Snowflake gera resume/suspend excessivo — cada resume
  tem custo mínimo de startup; equilibrar com o padrão real de uso.
- Z-ORDER/OPTIMIZE em Databricks tem custo de compute próprio — rodar em excesso (a cada
  micro-batch) pode custar mais do que economiza; agendar periodicamente (diário/semanal), não a
  cada write.
- BigQuery: `SELECT *` mesmo em tabela particionada e clusterizada ainda escaneia todas as
  colunas — sempre selecionar só as colunas necessárias (BigQuery cobra por coluna escaneada, não
  só por linha).
