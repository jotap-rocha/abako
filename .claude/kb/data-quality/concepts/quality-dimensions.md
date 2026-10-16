# Dimensões de Qualidade de Dados

## As 5 dimensões formais

Framework padrão de mercado (DAMA-DMBOK) para classificar todo check de qualidade em uma
dimensão nomeada — isso é o que separa "regra solta" de "framework de qualidade auditável".

| Dimensão | Pergunta que responde | Métrica |
|---|---|---|
| **Completude** | Os campos obrigatórios estão preenchidos? | % de não-nulos em campo required |
| **Unicidade** | Existem duplicatas indevidas? | % de registros únicos por chave de negócio |
| **Validade** | O valor respeita formato/domínio/range? | % de valores dentro do domínio esperado |
| **Consistência** | O dado bate entre campos/sistemas relacionados? | % de registros sem contradição cross-field/cross-source |
| **Atualidade** | O dado está fresco o suficiente para o SLA? | idade do dado vs SLA de freshness declarado |

## Completude (Completeness)

```sql
SELECT
  count(*) AS total,
  count(order_id) AS non_null,
  round(count(order_id) * 100.0 / count(*), 2) AS completeness_pct
FROM orders_silver;
```

Alvo típico: `> 99%` em campos `required: true` do contrato. Nem todo campo precisa de 100% —
campos opcionais (ex.: `coupon_code`) toleram completude baixa por natureza do negócio.

## Unicidade (Uniqueness)

```sql
SELECT order_id, count(*) AS dup_count
FROM orders_silver
GROUP BY order_id
HAVING count(*) > 1;
```

Sempre defina a **chave de negócio** antes de medir — unicidade sem chave declarada é ambígua
(linha inteira idêntica é caso raro; a duplicata real é por PK de negócio).

## Validade (Validity)

Conformidade a formato, enum, range ou regex declarado no contrato.

```sql
SELECT count(*) AS invalid_count
FROM orders_silver
WHERE status NOT IN ('pending', 'confirmed', 'shipped', 'delivered', 'cancelled')
   OR amount <= 0;
```

Validade é a dimensão mais fácil de testar com ferramentas declarativas (Great Expectations,
Soda, dbt `accepted_values`) — ver `patterns/` deste domínio.

## Consistência (Consistency)

Coerência entre campos do mesmo registro ou entre tabelas/sistemas relacionados.

```sql
-- shipped_at só pode existir se status já passou por 'shipped'
SELECT count(*) AS inconsistent
FROM orders_silver
WHERE shipped_at IS NOT NULL
  AND status NOT IN ('shipped', 'delivered');
```

Consistência cross-source (ex.: total do pedido no ERP == total no data warehouse) exige
reconciliação — geralmente fora do escopo de um único check declarativo, entra como pattern de
reconciliação em pipeline dedicado.

## Atualidade (Timeliness / Freshness)

```sql
SELECT max(_ingested_at) AS last_load,
       datediff(hour, max(_ingested_at), current_timestamp()) AS hours_stale
FROM orders_silver;
```

Compare `hours_stale` contra o `sla.freshness` declarado no data contract
(ver `concepts/data-contracts-odcs.md`). Atualidade é a dimensão central de
`concepts/pipeline-observability.md`.

## Gotchas

- **Métrica sem threshold não é check** — toda dimensão precisa de um limiar declarado
  (ex.: completude `> 99%`), senão vira número decorativo sem ação associada.
- **Validade ≠ Consistência** — um valor pode ser individualmente válido (status existe no enum)
  e ainda ser inconsistente com outro campo do mesmo registro.
- **Unicidade exige chave de negócio explícita** — nunca assuma "linha inteira" como chave.
- **Atualidade depende do relógio da fonte, não só do pipeline** — se a fonte já entrega dado
  atrasado, o pipeline não pode "consertar" atualidade, só reportar.
