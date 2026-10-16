---
topic: join-types-costs
confidence: null
mcp_validated: null
---

# Tipos de Join e seus Custos

## As três estratégias físicas (o planner escolhe uma para cada `JOIN` lógico)

`INNER JOIN`, `LEFT JOIN` etc. são operadores **lógicos** — o otimizador escolhe a
implementação **física**: nested loop, hash join ou merge join. Ler qual foi escolhida no
plano (ver `query-plan-reading.md`) é o primeiro passo para saber se o join está caro por
natureza do dado ou por falta de índice/estatística.

## Nested Loop

```
Para cada linha do lado externo:
    busca linha(s) correspondente(s) no lado interno
```
- **Custo**: `O(N × M)` sem índice; `O(N × log M)` com índice no lado interno (busca vira
  index scan em vez de scan completo por iteração).
- **Bom quando**: lado externo é pequeno (dezenas a poucas centenas de linhas) — típico em
  lookup por ID ou filtro muito seletivo aplicado antes do join.
- **Ruim quando**: lado externo é grande E lado interno não tem índice — cada iteração faz
  um scan completo da tabela interna, custo multiplicado por `loops=N` no plano.

```sql
-- Bom candidato a nested loop: filtro seletivo reduz o lado externo antes do join
SELECT p.*, c.nome
FROM pedidos p
JOIN clientes c ON c.id = p.cliente_id
WHERE p.id = 4521;   -- 1 linha do lado externo → nested loop com index scan em clientes é ótimo
```

## Hash Join

```
Constrói hash table em memória a partir do lado menor ("build")
Percorre o lado maior, sonda a hash table ("probe")
```
- **Custo**: `O(N + M)` — uma passada em cada lado, mas exige memória (`work_mem` no Postgres)
  proporcional ao lado menor. Se não couber em memória → spill to disk (`Hash Batches` > 1 no
  plano) — muito mais lento.
- **Bom quando**: sem ordem prévia útil, tabelas médias/grandes, sem índice utilizável no
  predicado de join.
- **Ruim quando**: `work_mem` insuficiente para a hash table → spill; ou lado "build" muito
  maior que o esperado (estimativa errada, ver `query-plan-reading.md`).

## Merge Join

```
Ambos os lados já ordenados pela chave de join (ou ordenados via Sort explícito)
Mescla como um "zip" de duas listas ordenadas
```
- **Custo**: `O(N + M)` para a mesclagem, mas soma o custo de ordenar cada lado se não já
  vier ordenado (`Sort` no plano antes do `Merge Join` — pode dominar o custo total).
- **Bom quando**: ambos os lados já saem ordenados de um índice (`Index Scan` que cobre a
  chave de join) — evita o `Sort` e vira quase gratuito.
- **Ruim quando**: precisa ordenar ambos os lados do zero — nesse caso hash join costuma
  vencer, a menos que o resultado final também precise vir ordenado por essa chave.

## Tabela de decisão rápida

| Situação | Estratégia provável | Ação se estiver errada |
|---|---|---|
| Lado externo pequeno, índice no lado interno | Nested Loop | Se veio Seq Scan no interno: falta índice |
| Tabelas grandes, sem ordem prévia | Hash Join | Se `Hash Batches > 1`: aumentar `work_mem` ou filtrar antes |
| Ambos lados já ordenados/indexados na chave | Merge Join | Se apareceu `Sort` caro antes: criar índice cobrindo a chave |
| Estimativa de linhas muito errada | Qualquer um, mas mal escolhido | `ANALYZE tabela` — estatísticas desatualizadas |

## Ordem de JOIN em múltiplas tabelas

O otimizador reordena joins automaticamente (dentro de um limite de tabelas — Postgres usa
busca exaustiva até `join_collapse_limit`, default 8; acima disso usa heurística genética).
Reescrever a ordem manual raramente ajuda em Postgres/Snowflake/BigQuery modernos — é mais
produtivo garantir estatísticas atualizadas e índices corretos do que tentar "adivinhar" a
ordem ideal.

## Engines colunares (Snowflake/BigQuery) — o que muda

Nesses engines, joins grandes frequentemente envolvem **shuffle** (redistribuição de dados
entre nós de computação) — o equivalente ao "custo de hash join" inclui também o custo de
mover dados pela rede. Um join entre uma tabela particionada/clusterizada pela chave de join
e outra não, tende a gerar shuffle assimétrico — ver profile de execução (Snowflake Query
Profile, BigQuery Execution Details) para localizar o estágio de shuffle dominante.

## Gotchas

- `LEFT JOIN` com filtro no `WHERE` sobre a tabela do lado direito vira `INNER JOIN` de fato
  (perde as linhas `NULL` do preenchimento) — filtro de tabela do lado direito deve ir no
  `ON`, não no `WHERE`, se a intenção é preservar o `LEFT`.
- Join em colunas de tipos diferentes (ex.: `int` vs `text`) impede uso de índice — cast
  implícito força scan completo em muitos engines.
- Função aplicada à coluna de join (`ON LOWER(a.email) = LOWER(b.email)`) impede index scan
  a menos que exista índice de expressão (`CREATE INDEX ON tabela (LOWER(email))`).

## Referências
- `query-plan-reading.md` — como identificar qual estratégia o plano escolheu
- `../patterns/composite-indexing.md` — como criar índice que habilita merge/nested loop eficiente
