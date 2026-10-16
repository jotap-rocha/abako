---
domain: data-modeling
description: "Modelagem dimensional e Data Vault — star/snowflake schema, SCD, grão de fato, bridge tables"
mcp_validated: null
confidence: null
---

# KB: Data Modeling — Índice

Base de conhecimento de modelagem de dados para data warehouse / lakehouse: modelagem
dimensional (Kimball), Data Vault 2.0, e os padrões de implementação recorrentes (SCD,
accumulating snapshot, bridge table).

## Conformidade DE (ponte)

Fonte: `data-engineering.yaml` — este KB **não** duplica severidade nem texto normativo.

| Âncora | Relação |
|---|---|
| `DE-A*` | Universal |
| `DE-D004` | schema rescue (evolução / contrato de schema) |

## Learning path

1. `concepts/grain-granularity.md` — sempre comece aqui: sem grão definido, nenhum modelo é
   correto.
2. `concepts/star-vs-snowflake.md` — a decisão estrutural mais comum na camada de apresentação.
3. `concepts/scd-types.md` — como tratar mudança de atributo em dimensão.
4. `concepts/data-vault-2.md` — só se o projeto tem múltiplas fontes heterogêneas e exige
   auditabilidade forte na camada de integração.

## Conceitos

| Arquivo | Tópico |
|---|---|
| [star-vs-snowflake.md](concepts/star-vs-snowflake.md) | Desnormalizado vs normalizado, quando usar cada um |
| [data-vault-2.md](concepts/data-vault-2.md) | Hubs, Links, Satellites — camada de integração auditável |
| [scd-types.md](concepts/scd-types.md) | Slowly Changing Dimension — tipos 0 a 6 |
| [grain-granularity.md](concepts/grain-granularity.md) | Grão de fato, os 3 tipos de fact table, erros comuns |

## Padrões

| Arquivo | Tópico |
|---|---|
| [star-schema-design.md](patterns/star-schema-design.md) | Processo Kimball de 4 passos com exemplo completo |
| [scd-type-2.md](patterns/scd-type-2.md) | Implementação de SCD Type 2 (MERGE, hash_diff, join com fact) |
| [accumulating-snapshot.md](patterns/accumulating-snapshot.md) | Fact table de processo com estágios (fulfillment, funil) |
| [bridge-table.md](patterns/bridge-table.md) | Relações many-to-many, weighting factor, hierarquias |

## Capability map

| Preciso de... | Vou em... |
|---|---|
| Decidir star vs snowflake | `concepts/star-vs-snowflake.md` |
| Desenhar um star schema do zero | `patterns/star-schema-design.md` |
| Versionar histórico de uma dimensão | `concepts/scd-types.md` + `patterns/scd-type-2.md` |
| Modelar processo com etapas (pedido, funil, esteira) | `patterns/accumulating-snapshot.md` |
| Resolver relação N:N sem duplicar medida | `patterns/bridge-table.md` |
| Modelar camada de integração multi-fonte auditável | `concepts/data-vault-2.md` |
| Definir o que é "uma linha" de uma fact table | `concepts/grain-granularity.md` |

## Quick Reference

Ver [quick-reference.md](quick-reference.md) — tabela de decisão star/snowflake, tabela dos
tipos de SCD e checklist de grão. Ler só se a tarefa exigir esse nível de detalhe.

## Status de validação

Este domínio ainda não passou por validação via Context-7 MCP (ferramenta indisponível no
momento da criação) — `mcp_validated: null`, `confidence: null` no frontmatter e no
`_index.yaml`. Conteúdo baseado em metodologia estabelecida (Kimball, Linstedt) e prática de
mercado; recomenda-se rodar o Modo 2 (auditoria) deste skill assim que o Context-7 MCP estiver
acessível, para elevar a confiança antes de vincular um agente de domínio (`schema-designer`).
