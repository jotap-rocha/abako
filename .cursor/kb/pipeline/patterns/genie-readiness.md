# Genie readiness — salas NL e governança semântica

## Quando usar

Acione no **harness-define** quando gate T8 (Genie/NL) = **sim** em projeto pipeline.

Complementa gates G1–G7 de [medallion-sdd-gates.md](medallion-sdd-gates.md).

## Checklist Genie / NL

| # | Item | Obrigatório se Genie |
|---|---|---|
| GR1 | Tabelas Gold expostas listadas | Sim |
| GR2 | **Comment/descrição** por tabela (UC ou glossary) | Sim |
| GR3 | **Comment/descrição** por coluna exposta | Sim |
| GR4 | Nomes amigáveis (`display_name`) para termos de negócio | Recomendado |
| GR5 | Relacionamentos documentados (PK/FK ou negócio) | Sim |
| GR6 | Métricas e sinônimos (camada semântica) | Se métricas calculadas |
| GR7 | Glossário / ontologia de domínio | Se domínio complexo (seguros, titular/beneficiário) |
| GR8 | Classificação e owner UC | Sim |
| GR9 | Sem colunas multivaloradas na Gold exposta | Sim |
| GR10 | PII mascarado ou excluído da sala NL | Se PII no domínio |

## Relacionamentos de negócio (exemplos)

Documentar explicitamente no grill/PRD:

- Titular ↔ beneficiário (seguros)
- Titular ↔ adicional (cartão)
- Cliente ↔ vendedor
- Empresa contratante ↔ contratada

Formato sugerido:

```yaml
relationships:
  - from: gold.clientes.cliente_id
    to: gold.pedidos.cliente_id
    type: one_to_many
    business_label: "cliente realiza pedidos"
```

## Camada semântica vs ontologia

| Camada | Conteúdo | Quando |
|---|---|---|
| **Semântica** | Métricas, sinônimos, unidades, fórmulas | BI + Genie com KPIs |
| **Ontologia** | Conceitos, hierarquias, regras de domínio | Domínio rico, múltiplos papéis de entidade |

## Integração harness

- Brainstorm T8 pergunta se há Genie/NL
- Define valida G1–G7 + este checklist
- Gold analítico: [gold-analytic.md](../concepts/gold-analytic.md)

## Ver também

- [medallion-sdd-gates.md](medallion-sdd-gates.md) — gates Gold + NL
- [data-contracts.md](../concepts/data-contracts.md) — contratos e consumer
