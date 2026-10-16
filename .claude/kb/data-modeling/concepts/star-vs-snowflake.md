# Star Schema vs Snowflake Schema

## O que são

Ambos são modelos dimensionais (Kimball) organizados em **fato** (eventos/medidas numéricas) +
**dimensões** (contexto descritivo). A diferença está em como as dimensões são normalizadas.

## Star Schema

Dimensões **desnormalizadas** — cada dimensão é uma única tabela larga, sem tabelas de apoio.

```
        dim_customer
             |
dim_date -- fact_sales -- dim_product
             |
        dim_store
```

- **Vantagens**: menos joins (query mais simples e rápida), mais fácil de entender para
  analistas de negócio, melhor performance em engines colunares (BigQuery, Redshift, Databricks
  SQL Warehouse) onde joins largos custam menos que múltiplos joins pequenos.
- **Desvantagens**: redundância de dados na dimensão (ex.: `dim_product` repete `category_name`
  em toda linha de produto daquela categoria) — mais espaço, mais custo de atualização.

## Snowflake Schema

Dimensões **normalizadas** — uma dimensão se divide em sub-tabelas hierárquicas (ex.:
`dim_product` → `dim_category` → `dim_department`).

```
dim_department -- dim_category -- dim_product -- fact_sales -- dim_customer
```

- **Vantagens**: elimina redundância, mais fácil manter integridade referencial em hierarquias
  profundas, menor espaço em disco.
- **Desvantagens**: mais joins por query (impacto de performance, especialmente em engines
  orientadas a linha), mais complexo para analistas de negócio escreverem SQL ad-hoc.

## Quando usar cada um

| Critério | Star | Snowflake |
|---|---|---|
| Motor de consulta colunar (Databricks, BigQuery, Redshift, Snowflake) | Preferir | Evitar |
| Dimensão com hierarquia profunda e mutável (ex.: geografia com 5 níveis) | Aceitável | Preferir |
| Self-service BI (Power BI, Tableau, Looker) direto nas tabelas | Preferir | Evitar |
| Espaço em disco é restrição real (raro hoje em lakehouses) | Evitar | Preferir |

**Regra prática em ambientes lakehouse modernos (Delta Lake, Databricks, Snowflake):** default
para star schema. Armazenamento é barato; joins extras custam mais que a redundância economiza.
Snowflake schema só se justifica quando a hierarquia da dimensão muda com frequência e a
duplicação geraria inconsistência real de manutenção.

## Gotchas

- Não confundir "Snowflake Schema" (padrão de modelagem) com "Snowflake" (o produto de data
  warehouse) — são coisas diferentes com o mesmo nome.
- Star schema não significa "sem nenhuma normalização" — a fact table em si já é altamente
  normalizada (grão único, chaves estrangeiras para dimensões).
- Um schema pode ser "parcialmente snowflaked": normalizar só a dimensão que realmente tem
  hierarquia volátil, manter as demais como star. Isso é comum e válido — não é tudo ou nada.
