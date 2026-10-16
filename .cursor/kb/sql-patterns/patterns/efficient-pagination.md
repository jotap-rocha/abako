---
topic: efficient-pagination
confidence: null
mcp_validated: null
---

# Paginação Eficiente — Cursor/Keyset vs Offset (análise de custo)

> A sintaxe básica de `LIMIT/OFFSET` vs cursor já está em
> `.claude/agents/architect/sql-architect.md` ("Padrões recorrentes → Paginação com cursor").
> Este arquivo cobre o **porquê** do custo, o caso de múltiplas colunas e onde cada abordagem
> quebra — não repete a sintaxe básica de lá.

## Por que `OFFSET` degrada com página alta

`OFFSET N` não "pula" para a linha N — o engine **lê e descarta** as N linhas anteriores antes
de começar a devolver resultado. Página 1 (`OFFSET 0`) é O(LIMIT); página 10.000
(`OFFSET 500000`) é O(500000 + LIMIT).

```
EXPLAIN ANALYZE SELECT * FROM pedidos ORDER BY created_at DESC LIMIT 20 OFFSET 500000;
-- actual rows processados internamente ≈ 500020, mesmo devolvendo só 20
```

No plano, isso aparece como um nó que processa muito mais linhas do que o `LIMIT` final —
mesmo com índice cobrindo o `ORDER BY`, o engine ainda percorre (ou pula via índice, mais
barato mas não gratuito) as 500.000 primeiras entradas do índice antes de chegar na página.

## Keyset/cursor: por que não degrada

Keyset pagination transforma "pule N linhas" em "busque linhas depois deste valor", que o
índice resolve diretamente via seek — custo praticamente constante independente da página.

```sql
-- Página N via OFFSET: custo cresce com N
SELECT id, created_at FROM pedidos ORDER BY created_at DESC, id DESC LIMIT 20 OFFSET 500000;

-- Mesma página via keyset: custo ~constante (seek direto no índice)
SELECT id, created_at FROM pedidos
WHERE (created_at, id) < ($cursor_created_at, $cursor_id)
ORDER BY created_at DESC, id DESC
LIMIT 20;
```

## Requisito: chave de ordenação estável e única

Keyset só funciona se `ORDER BY` é **determinístico** — se ordenar só por `created_at` e
houver timestamps duplicados, linhas podem ser puladas ou repetidas entre páginas. Sempre
combine uma coluna que pode repetir com uma chave única como tiebreaker:

```sql
ORDER BY created_at DESC, id DESC   -- id garante ordem total, mesmo com created_at empatado
```

Comparação de tupla (`WHERE (created_at, id) < (...)`) é suportada nativamente em Postgres e
DuckDB; para engines sem comparação de tupla nativa em todas as versões, expanda manualmente:

```sql
WHERE created_at < $cursor_created_at
   OR (created_at = $cursor_created_at AND id < $cursor_id)
```

## Índice necessário

Keyset só é rápido se existir índice composto cobrindo exatamente a mesma ordem do `ORDER BY`
(ver `composite-indexing.md`):

```sql
CREATE INDEX idx_pedidos_cursor ON pedidos (created_at DESC, id DESC);
```
Sem esse índice, keyset ainda funciona corretamente mas não ganha nada em performance —
vira scan + filter como qualquer outro predicado.

## Quando `OFFSET` ainda é aceitável

- Volume pequeno (tabela cabe toda em cache, ou dataset com poucas centenas/milhares de linhas).
- UI que precisa de "pular para página N" arbitrária (ex.: "ir para página 47") — keyset não
  suporta salto arbitrário, só "próxima"/"anterior" a partir de um cursor conhecido.
- Primeiras páginas de listagens onde o usuário raramente passa da página 3-5 na prática.

## Quando migrar para keyset é obrigatório

- Scroll infinito / "carregar mais" — não precisa de salto arbitrário, cursor natural.
- API pública ou export de dataset grande — página alta é certeza, não exceção.
- Job de reprocessamento/paginação de milhões de linhas — `OFFSET` alto pode dominar o tempo
  total do job inteiro.

## Cross-engine

Sintaxe de comparação de tupla e `LIMIT/OFFSET` é equivalente nos 4 engines (Postgres,
Snowflake, BigQuery, DuckDB) — ver `dialect-translation.md` para diferenças de função de
data usadas em cursores baseados em timestamp. Em BigQuery, paginação por `OFFSET` em
tabelas muito grandes também tem custo em **bytes processados** (custo $), não só latência —
motivo a mais para preferir keyset em pipelines de leitura frequente.

## Referências
- `.claude/agents/architect/sql-architect.md` — sintaxe básica de cursor pagination
- `composite-indexing.md` — índice composto que sustenta o keyset
- `slow-query-diagnosis.md` — passo 3, como identificar `OFFSET` alto no sintoma
