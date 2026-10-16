---
topic: compaction-small-files
confidence: null
mcp_validated: null
---

# Compaction / Otimização de Arquivos Pequenos

## O problema

Escritas frequentes e de baixo volume (streaming, micro-batch, upserts merge-on-read) geram
muitos arquivos Parquet pequenos. Isso degrada leitura de duas formas: overhead de abrir/fechar
milhares de arquivos pequenos (custo fixo por arquivo domina sobre custo de dado lido) e, em
merge-on-read, acúmulo de delete files/deletion vectors que o motor precisa aplicar a cada
leitura antes de servir a query.

Regra prática: arquivos abaixo de ~64-128 MB (a depender do motor) geram overhead desproporcional
— compaction reagrupa arquivos pequenos em arquivos no tamanho-alvo.

## Estratégias de compaction

| Estratégia | O que faz | Quando usar |
|---|---|---|
| Bin-packing | Agrupa arquivos pequenos em arquivos maiores, sem reordenar dados | Caso geral, mais barato |
| Sort-based | Reescreve ordenando por uma ou mais colunas | Queries com filtro seletivo em coluna específica |
| Z-order / Hilbert curve | Ordena por múltiplas colunas preservando localidade multi-dimensional | Filtros combinados em 2+ colunas de baixa correlação |
| Liquid clustering (Delta) | Reclustering incremental, substitui partição + Z-order | Cargas com padrão de query evolutivo, sem fixar partition scheme |

## Iceberg

```sql
-- Bin-pack (padrão)
CALL catalog.system.rewrite_data_files(
    table => 'db.orders',
    strategy => 'binpack',
    options => map('target-file-size-bytes', '134217728')  -- 128MB
);

-- Sort por coluna de filtro frequente
CALL catalog.system.rewrite_data_files(
    table => 'db.orders',
    strategy => 'sort',
    sort_order => 'customer_id ASC'
);

-- Compactar também delete files acumulados (merge-on-read)
CALL catalog.system.rewrite_position_delete_files(table => 'db.orders');
```

## Delta Lake

```sql
-- OPTIMIZE clássico (bin-pack)
OPTIMIZE db.orders;

-- Com Z-order
OPTIMIZE db.orders ZORDER BY (customer_id, order_date);

-- Liquid clustering (substitui partição + Z-order em versões recentes)
ALTER TABLE db.orders CLUSTER BY (customer_id, order_date);
OPTIMIZE db.orders;  -- aplica o reclustering incrementalmente
```

## Hudi

Compaction é parte do **clustering service** — pode rodar inline (síncrono, no próprio job de
escrita) ou async (job separado, não bloqueia ingestão). Para workloads de upsert intensivo
(merge-on-read), compaction async é o padrão recomendado para não penalizar a latência de escrita.

## Agendamento

- **Não rodar a cada escrita**: compaction tem custo (reescreve dados) — rodar por job agendado
  (ex.: horário/diário) ou por trigger de threshold (nº de arquivos pequenos acima de X).
- **Streaming**: compaction deve ser assíncrona, em job separado do pipeline de ingestão — rodar
  inline em cada micro-batch derrota o propósito de baixa latência do streaming.
- **Custo vs benefício**: compaction reescreve arquivos, o que gera novos snapshots — coordenar
  com a política de retenção (`patterns/retention-vacuum.md`) para não inflar o histórico de
  snapshots desnecessariamente.

## Gotchas

- Compaction **não é grátis em compute**: reescrever TBs de dados frequentemente pode custar mais
  do que o ganho de leitura, se a tabela não é lida com frequência suficiente para compensar.
- Rodar compaction concorrente com escritas ativas pode gerar conflitos de commit (retry) — em
  tabelas de altíssima concorrência, agendar em janela de menor contenção.
- Z-order/sort-based compaction degrada com o tempo à medida que novos dados chegam
  desordenados — precisa recompactar periodicamente, não é "faça uma vez e esqueça".
