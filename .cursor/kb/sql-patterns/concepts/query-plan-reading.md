---
topic: query-plan-reading
confidence: null
mcp_validated: null
---

# Leitura de Query Plan (EXPLAIN ANALYZE)

## Por que ler o plano, não só o tempo

O tempo total diz *que* está lento; o plano diz *onde* e *por quê*. Sem o plano, otimização
vira tentativa e erro (adicionar índice às cegas, reescrever query sem saber o gargalo real).

## Postgres: `EXPLAIN (ANALYZE, BUFFERS)`

```sql
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT p.id, p.nome, c.nome AS categoria
FROM produtos p
JOIN categorias c ON c.id = p.categoria_id
WHERE p.tenant_id = 'abc' AND p.ativo = true
ORDER BY p.nome
LIMIT 50;
```

Saída (trecho):
```
Limit  (cost=1250.45..1250.57 rows=50 width=64) (actual time=45.2..45.3 rows=50 loops=1)
  ->  Sort  (cost=1250.45..1265.12 rows=5868 width=64) (actual time=45.1..45.2 rows=50 loops=1)
        Sort Key: p.nome
        Sort Method: top-N heapsort  Memory: 28kB
        ->  Hash Join  (cost=25.5..980.3 rows=5868 width=64) (actual time=0.5..38.9 rows=5900 loops=1)
              Hash Cond: (p.categoria_id = c.id)
              ->  Seq Scan on produtos p  (cost=0..900.0 rows=5868 width=48)
                    (actual time=0.1..30.2 rows=5900 loops=1)
                    Filter: (tenant_id = 'abc' AND ativo)
                    Rows Removed by Filter: 44100
              ->  Hash  (cost=20.0..20.0 rows=440 width=24) (actual time=0.3..0.3 rows=440 loops=1)
Planning Time: 0.4 ms
Execution Time: 45.5 ms
```

### Como ler, campo por campo

| Campo | Significado |
|---|---|
| `cost=X..Y` | Custo **estimado** (startup..total), em unidades arbitrárias do planner — não é ms |
| `rows=N` | Linhas **estimadas** pelo planner para esse nó |
| `actual time=X..Y` | Tempo **real** (ms), medido em `ANALYZE` — startup..total |
| `actual rows=N` | Linhas **reais** retornadas — comparar com `rows` estimado |
| `loops=N` | Quantas vezes o nó executou (> 1 em nested loop = multiplica o tempo) |
| `Rows Removed by Filter` | Linhas lidas e descartadas — sinal de scan ineficiente |

### O sinal mais importante: estimado vs real

```
rows=5868 (estimado)  vs  actual rows=5900 (real)  → OK, estatísticas boas
rows=50 (estimado)    vs  actual rows=50000 (real)  → estatísticas desatualizadas ou
                                                        predicado não sargeável
```
Gap grande entre estimado e real é a causa nº 1 de plano ruim escolhido pelo otimizador —
ele decide nested loop vs hash join com base na estimativa errada.

## Snowflake, BigQuery, DuckDB — o que muda

| Engine | Comando | Particularidade |
|---|---|---|
| Snowflake | `EXPLAIN` + Query Profile (UI) | Profile mostra % de tempo por operador, spill to disk, bytes scanned |
| BigQuery | `EXPLAIN` / aba "Execution details" | Foco em bytes processados (custo $) e estágios (shuffle) por slot |
| DuckDB | `EXPLAIN ANALYZE` | Formato em árvore similar ao Postgres; mostra cardinalidade por operador |

Nesses engines colunar/MPP, o sinal equivalente a "Seq Scan ruim" é **bytes scanned** alto
sem particionamento/clustering — não existe "índice" tradicional, e sim clustering keys
(Snowflake) ou particionamento + clustering de tabela (BigQuery).

## Gotchas

- `EXPLAIN` sem `ANALYZE` só mostra estimativa — nunca confie nele sozinho para diagnosticar
  produção; ele não executa a query.
- `EXPLAIN ANALYZE` **executa a query de verdade** — cuidado com `INSERT/UPDATE/DELETE`, use
  transação com `ROLLBACK` ou rode só em `SELECT`.
- `BUFFERS` (Postgres) revela cache hit ratio — `shared hit` alto é bom, `read` alto é I/O de disco.
- Custo estimado alto não significa tempo real alto — sempre compare com `actual time`.

## Referências
- `join-types-costs.md` — como interpretar `Hash Join`/`Nested Loop`/`Merge Join` no plano
- `../patterns/slow-query-diagnosis.md` — checklist que usa este arquivo como passo 1
