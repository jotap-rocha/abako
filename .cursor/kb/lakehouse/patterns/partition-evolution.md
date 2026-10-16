---
topic: partition-evolution
confidence: null
mcp_validated: null
---

# Particionamento Evolutivo (Partition Evolution)

## Problema que resolve

Em Hive tradicional, o partition scheme é fixo na criação da tabela e faz parte do schema
lógico — mudar de partição por `dia` para partição por `hora`, ou de `mês` para `dia`, exige
reescrever a tabela inteira (`CTAS` para uma nova tabela + swap + backfill). Isso é caro em
tabelas grandes e bloqueia a decisão de "acertar o particionamento" até ter volume/padrão de
query suficiente para saber qual scheme é o certo.

Iceberg é o formato com suporte nativo mais maduro a **partition evolution**: a tabela pode mudar
seu partition spec ao longo do tempo sem reescrever dados antigos. Cada arquivo de dados carrega
consigo o spec sob o qual foi escrito; o motor de query reconcilia specs diferentes na hora do
planejamento.

## Como funciona

1. Dados escritos sob o spec V1 (ex.: partição por `month(created_at)`) continuam existindo com
   esse spec — **não são reescritos**.
2. `ALTER TABLE ... ADD PARTITION FIELD` registra um novo spec V2 (ex.: adiciona
   `day(created_at)`), que passa a valer só para escritas **novas**.
3. Queries que filtram por `created_at` se beneficiam de partition pruning em ambos os specs —
   o planner do Iceberg sabe qual spec cada arquivo usa.

```sql
-- Estado inicial: particionado por mês
CREATE TABLE catalog.db.events (
    event_id BIGINT,
    created_at TIMESTAMP,
    payload STRING
)
USING iceberg
PARTITIONED BY (month(created_at));

-- Volume cresceu, granularidade mensal ficou grossa demais.
-- Evolui o spec SEM reescrever os dados já gravados:
ALTER TABLE catalog.db.events
    ADD PARTITION FIELD day(created_at);

-- Opcional: remover o campo antigo do spec ATIVO
-- (dados antigos continuam legíveis pelo spec com que foram escritos)
ALTER TABLE catalog.db.events
    DROP PARTITION FIELD month(created_at);
```

## Hidden partitioning

Diferente de Hive (onde a coluna de partição precisa existir fisicamente e o usuário escreve
`WHERE year=2026 AND month=07`), Iceberg deriva a partição de uma expressão sobre a coluna real
(`month(created_at)`, `bucket(16, customer_id)`, `truncate(10, order_id)`). O usuário sempre
filtra pela coluna de negócio (`WHERE created_at >= ...`) — o pruning acontece por trás, sem
precisar saber o partition scheme.

## Quando usar bucket vs truncate vs time-based

| Transform | Uso típico | Exemplo |
|---|---|---|
| `year/month/day/hour(coluna)` | Séries temporais, dados de ingestão contínua | `day(created_at)` |
| `bucket(N, coluna)` | Alta cardinalidade sem ordem natural (IDs), evita partições minúsculas | `bucket(32, customer_id)` |
| `truncate(N, coluna)` | Strings/números com prefixo significativo | `truncate(3, zip_code)` |
| `identity(coluna)` | Cardinalidade baixa e conhecida | `identity(country)` |

## Outros formatos

- **Delta Lake**: não tem partition evolution nativa no mesmo sentido — a alternativa moderna é
  **liquid clustering** (`CLUSTER BY`), que reorganiza dados por chaves de clustering sem exigir
  partition scheme fixo, mas é um mecanismo diferente (clustering, não partition spec versionado).
- **Hudi**: particionamento é definido na criação; mudanças exigem reparticionamento manual via
  clustering service ou reescrita.

## Gotchas

- Partition evolution **não retroage**: dados antigos não migram para o novo spec automaticamente
  — se a query depende de pruning eficiente também nos dados antigos, é preciso compactar/reescrever
  esses arquivos deliberadamente (ver `patterns/compaction-small-files.md`), não é automático.
- Evoluir partição com granularidade **maior** (ex.: mês → ano) pode agrupar arquivos que antes
  estavam em partições separadas — validar que os writers não vão gerar partições gigantes.
- Excesso de partition fields adicionados ao longo do tempo aumenta a complexidade de metadados
  (mais specs para o planner reconciliar) — evolua com intenção, não a cada sprint.
