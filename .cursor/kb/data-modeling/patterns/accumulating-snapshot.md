# Accumulating Snapshot Fact Table

Ver `concepts/grain-granularity.md` para os 3 tipos de fact table. Este pattern cobre o
accumulating snapshot — usado para processos com **início, fim e estágios intermediários bem
definidos** (pedido → separação → envio → entrega; lead → oportunidade → fechamento).

## Quando usar

- O processo de negócio tem um número finito e conhecido de estágios (ex.: fulfillment de
  pedido: `ordered → picked → packed → shipped → delivered`).
- Você precisa medir **lead time entre estágios** (ex.: "quanto tempo entre pedido e envio").
- Cada instância do processo (1 pedido) é rastreada por 1 única linha, que é **atualizada** (não
  inserida de novo) conforme avança de estágio — a única fact table onde `UPDATE` é normal e
  esperado.

## Schema

```sql
CREATE TABLE fact_order_fulfillment (
    order_sk            BIGINT PRIMARY KEY,   -- grão: 1 linha por pedido

    -- FK para dimensão de data, uma por estágio (todas nullable até o estágio ocorrer)
    order_date_sk       INT NOT NULL REFERENCES dim_date,
    picked_date_sk       INT REFERENCES dim_date,
    packed_date_sk       INT REFERENCES dim_date,
    shipped_date_sk      INT REFERENCES dim_date,
    delivered_date_sk    INT REFERENCES dim_date,

    -- FKs de contexto
    customer_sk          BIGINT NOT NULL REFERENCES dim_customer,
    warehouse_sk          BIGINT REFERENCES dim_warehouse,

    -- medidas de lead time (calculadas, denormalizadas para evitar recalcular em toda query)
    days_order_to_ship    INT,   -- NULL até shipped_date ser preenchido
    days_ship_to_deliver   INT,

    -- estado atual do processo
    current_status        STRING NOT NULL,     -- 'ordered' | 'picked' | ... | 'delivered' | 'cancelled'
    order_amount           DECIMAL(10,2) NOT NULL,

    _updated_at            TIMESTAMP NOT NULL
);
```

## Carga inicial (quando o processo começa)

```sql
INSERT INTO fact_order_fulfillment (
    order_sk, order_date_sk, customer_sk, current_status, order_amount, _updated_at
)
SELECT order_sk, date_sk, customer_sk, 'ordered', amount, current_timestamp()
FROM staging_new_orders;
```

## Atualização a cada estágio (o padrão central)

```sql
-- Databricks / Delta Lake MERGE — atualiza a linha existente ao avançar de estágio
MERGE INTO fact_order_fulfillment AS target
USING staging_shipped_events AS source
ON target.order_sk = source.order_sk

WHEN MATCHED THEN
  UPDATE SET
    target.shipped_date_sk       = source.event_date_sk,
    target.days_order_to_ship     = datediff(source.event_date, target.order_date),
    target.current_status         = 'shipped',
    target._updated_at            = current_timestamp();
```

Repita o `MERGE` para cada estágio (`picked`, `packed`, `delivered`) com sua própria fonte de
eventos — cada estágio é um job de pipeline separado que só faz `UPDATE`, nunca `INSERT`.

## Query típica habilitada por este padrão

```sql
-- Lead time médio de envio por warehouse, últimos 30 dias
SELECT
    w.warehouse_name,
    AVG(f.days_order_to_ship) AS avg_days_to_ship,
    COUNT(*) FILTER (WHERE f.current_status = 'cancelled') AS cancelled_count
FROM fact_order_fulfillment f
JOIN dim_warehouse w ON f.warehouse_sk = w.warehouse_sk
WHERE f.order_date_sk >= date_format(current_date() - INTERVAL 30 DAYS, 'yyyyMMdd')
GROUP BY w.warehouse_name;
```

## Gotchas

- É a **única** fact table onde `UPDATE` em linha existente é o padrão normal — em transaction
  fact e periodic snapshot, isso seria um erro de design. Não confunda os três tipos.
- Estágios que nunca ocorrem (ex.: pedido cancelado antes de `picked`) devem deixar as colunas
  de data subsequentes como `NULL`, não com valor sentinela (`0` ou `9999-12-31`) — sentinela
  quebra `AVG()`/`MIN()`/`MAX()` de lead time.
- Se o processo tem estágios **variáveis** (nem todo pedido passa pelas mesmas etapas, ex.:
  alguns pulam `packed`), considere modelar como transaction fact table de eventos (1 linha por
  mudança de estágio) e derivar o snapshot depois — accumulating snapshot pressupõe estágios
  fixos e conhecidos.
- Reprocessamento é sensível: se um evento de estágio chegar fora de ordem (ex.: `delivered`
  antes de `shipped` por atraso de fila), o `MERGE` pode sobrescrever com dado inconsistente —
  valide ordem de estágio na condição do `WHEN MATCHED`.
