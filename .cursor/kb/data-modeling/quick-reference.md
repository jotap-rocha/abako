---
domain: data-modeling
topic: quick-reference
---

# Data Modeling — Quick Reference

### Star vs Snowflake — decisão rápida

| Critério | Star | Snowflake |
|---|---|---|
| Engine colunar (Databricks, BigQuery, Snowflake, Redshift) | Preferir | Evitar |
| Self-service BI direto nas tabelas | Preferir | Evitar |
| Dimensão com hierarquia profunda e mutável | Aceitável | Preferir |
| Default em lakehouse moderno | **Sim** | Só com justificativa concreta |

### SCD — qual tipo usar

| Tipo | Histórico? | Quando |
|---|---|---|
| 0 | N/A | Atributo nunca muda (ex.: data de nascimento) |
| 1 | Não | Correção de erro, sem valor analítico histórico |
| 2 | Completo | **Default** — quase sempre a escolha certa |
| 3 | 1 versão anterior | Comparação pontual "antes vs depois" |
| 4 | Tabela separada | Volume alto de mudanças, separar quente/frio |
| 5 | Via mini-dim | Atributo muda com muita frequência |
| 6 | Híbrido (1+2+3) | Precisa histórico completo + estado atual na mesma linha |

### 3 tipos de fact table por grão

| Tipo | Grão | Exemplo |
|---|---|---|
| Transaction | 1 linha por evento discreto | 1 linha por venda |
| Periodic snapshot | 1 linha por entidade por período | 1 linha por conta por mês |
| Accumulating snapshot | 1 linha por instância de processo (UPDATE conforme avança) | 1 linha por pedido, colunas de data por estágio |

### Checklist: grão está definido?

- [ ] Consigo completar "uma linha nesta tabela representa exatamente ___"
- [ ] Nenhuma coluna mistura nível de detalhe diferente do grão (ex.: total do pedido numa
      fact de item)
- [ ] Toda dimensão usa surrogate key, não a chave natural da fonte

### Decision tree: preciso de bridge table?

```
Relação entre fact e dimensão é N:N (não 1:N)?
    ├── Não → join direto, sem bridge
    └── Sim
        ├── Query vai somar (SUM/AVG) uma medida numérica?
        │   └── Sim → bridge COM weighting_factor (soma = 1.0 por chave de fato)
        └── Query só filtra/lista (WHERE, EXISTS, DISTINCT)?
            └── bridge SEM weighting_factor é suficiente
```

### Data Vault 2.0 — quando vs star schema

| Cenário | Escolha |
|---|---|
| Múltiplas fontes heterogêneas, exigência de auditoria total | Data Vault 2.0 (camada de integração) |
| Fonte única estável, consumo direto por BI | Star schema |
| Sempre, na camada de apresentação final | Star schema (derivado do Vault, se houver) |
