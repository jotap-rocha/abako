# Design de Star Schema — Passo a Passo

Processo Kimball de 4 etapas aplicado a um caso real: vendas de e-commerce.

## Passo 1 — Escolher o processo de negócio

Um processo por fact table. Não modele "vendas + devoluções + estoque" numa fact só —
são processos diferentes, com grãos diferentes.

```
Processo escolhido: "venda de item em um pedido"
```

## Passo 2 — Declarar o grão

```
Grão: uma linha por item de linha de pedido (order line item)
```

## Passo 3 — Identificar dimensões

Toda pergunta de negócio ("por produto", "por loja", "por dia", "por cliente") vira uma
dimensão. Pergunte: "o que descreve o contexto deste evento?"

```sql
CREATE TABLE dim_date (
    date_sk         INT PRIMARY KEY,       -- surrogate key, formato YYYYMMDD
    full_date       DATE NOT NULL,
    day_of_week     STRING NOT NULL,
    month_name      STRING NOT NULL,
    quarter         INT NOT NULL,
    year            INT NOT NULL,
    is_weekend      BOOLEAN NOT NULL
);

CREATE TABLE dim_product (
    product_sk      BIGINT PRIMARY KEY,    -- surrogate key
    product_id      STRING NOT NULL,       -- natural key da fonte
    product_name    STRING NOT NULL,
    category        STRING NOT NULL,
    subcategory     STRING NOT NULL,
    brand           STRING NOT NULL,
    unit_cost       DECIMAL(10,2) NOT NULL
);

CREATE TABLE dim_customer (
    customer_sk     BIGINT PRIMARY KEY,
    customer_id     STRING NOT NULL,
    customer_name   STRING NOT NULL,
    segment         STRING NOT NULL,
    city            STRING NOT NULL,
    state           STRING NOT NULL
);

CREATE TABLE dim_store (
    store_sk        BIGINT PRIMARY KEY,
    store_id        STRING NOT NULL,
    store_name      STRING NOT NULL,
    region          STRING NOT NULL,
    channel         STRING NOT NULL        -- 'online' | 'physical'
);
```

**Sempre use surrogate key (`_sk`)** — nunca a chave natural da fonte como PK da dimensão.
Isso desacopla o modelo da fonte e viabiliza SCD Type 2 (múltiplas versões da mesma entidade).

## Passo 4 — Identificar fatos (medidas)

Fatos são numéricos e aditivos no grão declarado.

```sql
CREATE TABLE fact_sales (
    -- foreign keys para dimensões (todas obrigatórias, nunca NULL em star schema puro)
    date_sk         INT NOT NULL REFERENCES dim_date,
    product_sk      BIGINT NOT NULL REFERENCES dim_product,
    customer_sk     BIGINT NOT NULL REFERENCES dim_customer,
    store_sk        BIGINT NOT NULL REFERENCES dim_store,

    -- degenerate dimension: vive na fact, sem dimensão própria
    order_id        STRING NOT NULL,
    line_number     INT NOT NULL,

    -- medidas aditivas (podem ser somadas em qualquer dimensão)
    quantity        INT NOT NULL,
    unit_price      DECIMAL(10,2) NOT NULL,
    discount_amount DECIMAL(10,2) NOT NULL,
    net_revenue     DECIMAL(10,2) NOT NULL,

    _loaded_at      TIMESTAMP NOT NULL
);
```

## Classificando os fatos (aditividade)

| Tipo | Exemplo | Pode somar em qualquer dimensão? |
|---|---|---|
| Totalmente aditivo | `net_revenue`, `quantity` | Sim |
| Semi-aditivo | `account_balance` (soma faz sentido entre contas, não entre meses) | Só em algumas dimensões |
| Não-aditivo | `unit_price`, `discount_pct` | Não — usar `AVG()` ponderado ou não agregar |

## Query final — o motivo de fazer tudo isso

```sql
SELECT
    d.year, d.quarter,
    p.category,
    s.region,
    SUM(f.net_revenue) AS revenue,
    SUM(f.quantity)    AS units_sold
FROM fact_sales f
JOIN dim_date d    ON f.date_sk = d.date_sk
JOIN dim_product p ON f.product_sk = p.product_sk
JOIN dim_store s    ON f.store_sk = s.store_sk
WHERE d.year = 2026
GROUP BY d.year, d.quarter, p.category, s.region;
```

## Checklist antes de considerar o star schema "pronto"

- [ ] Grão declarado em uma frase, sem ambiguidade
- [ ] Toda dimensão usa surrogate key, não a chave natural
- [ ] Nenhuma coluna na fact table viola o grão (ex.: total do pedido numa fact de item)
- [ ] Fatos classificados por aditividade
- [ ] FKs de dimensão nunca NULL (se o contexto é desconhecido, use uma linha "Unknown" na
      dimensão — nunca NULL, que quebra INNER JOIN)
