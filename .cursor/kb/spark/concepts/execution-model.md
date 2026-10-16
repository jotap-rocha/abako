---
topic: execution-model
confidence: null
mcp_validated: null
---

# Modelo de Execução Distribuída

## Hierarquia: Job → Stage → Task

```
Ação (ex: .write(), .collect(), .count())
  └── Job
        └── Stage (fronteira = shuffle)
              └── Task (1 por partição)
```

- **Job**: disparado por uma ação. Uma aplicação Spark pode gerar muitos jobs.
- **Stage**: sequência de transformações que rodam sem shuffle. Um novo stage começa sempre que
  uma operação exige redistribuir dados entre partições (shuffle).
- **Task**: unidade de trabalho executada em 1 partição, em 1 core de 1 executor.

## Partições

- Unidade de paralelismo do Spark. Cada partição é processada por uma task, em paralelo com as
  outras.
- Nº de partições após leitura depende da fonte (ex: nº de arquivos/blocos no HDFS/S3).
- Nº de partições após um shuffle é controlado por `spark.sql.shuffle.partitions` (default 200) —
  quase sempre precisa ser ajustado para o tamanho real do cluster e dos dados.
- **Poucas partições** → subutiliza o cluster (paralelismo baixo, tasks gigantes, spill para disco).
- **Partições demais** → overhead de scheduling supera o ganho de paralelismo (tasks minúsculas).

## Shuffle — a operação mais cara do Spark

Shuffle acontece quando dados precisam ser redistribuídos entre partições porque a operação
depende de todos os registros de uma chave estarem juntos. Exemplos que disparam shuffle:

- `groupBy`, `join` (exceto broadcast), `distinct`, `orderBy`/`sort`, `repartition`

Custo do shuffle: serialização + escrita em disco local (shuffle files) + transferência de rede
entre executores + deserialização no destino. É I/O de disco e rede, não CPU — por isso é
tipicamente o gargalo nº 1 de performance em Spark.

```python
# Cada uma destas linhas fecha um stage e abre outro (shuffle boundary):
df.groupBy("customer_id").agg(sum("amount"))
df.join(other_df, "customer_id")   # quando NÃO é broadcast
df.orderBy("created_at")
df.repartition(200)
```

## Executors e cores

- Um **executor** é um processo JVM alocado em um worker node, com sua própria fatia de memória
  e um nº fixo de cores.
- Cada core de um executor processa 1 task por vez — nº de tasks paralelas = soma de cores de
  todos os executors ativos.
- Ver [memory-management.md](memory-management.md) para como a memória do executor é dividida, e
  [cluster-tuning.md](../patterns/cluster-tuning.md) para dimensionar cores/memory por executor.

## Gotchas

- Um job "lento" quase sempre significa: poucas partições (task gigante), skew (uma task muito
  maior que as outras), ou shuffle desnecessário — não é falta de mais executors.
- `spark.sql.shuffle.partitions=200` é o default histórico do Spark 1.x/2.x e raramente é o valor
  certo para clusters modernos — sempre revisar.
- Aumentar nº de executors não ajuda se o gargalo é 1 task grande (skew) — mais paralelismo não
  divide uma partição desbalanceada.
