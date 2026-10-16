# Gold analítico (antes de Diamond)

## O que é

Camada **Gold** no harness: subset de colunas relevantes para **negócio**, otimizado para
exploração ad-hoc, dashboards e salas de perguntas em linguagem natural (ex.: Databricks Genie).

**Não confundir** com:
- **Silver** — dados limpos, flat, contrato ODCS completo
- **Diamond** — modelo multidimensional (fatos/dimensões, star schema)

```text
Silver (completo, contrato) → Gold (subset analítico) → Diamond (dimensional)
```

## Responsabilidades

| Faz | Não faz |
|---|---|
| Selecionar colunas de negócio | Limpeza/validação (Silver) |
| Renomear para consumo (`display_name` opcional) | Agregações dimensionais pesadas (Diamond) |
| Descrições para LLM/BI | Normalizar JSON (Silver) |
| Views/tabelas para Genie | Tipagem primária (Bronze/Silver) |

## Colunas

- Dados: **somente** colunas acordadas no gate Gold (G1)
- Lineage: `_updated_at` obrigatório
- Opcional: `_gold_published_at`, `_consumer_tags`

## Contrato de consumo

Documento leve (YAML ou comments UC) listando:
- Colunas expostas + descrição de negócio
- Relacionamentos para join explícito (G4)
- Consumidores: BI, ad-hoc, Genie (G2)

Gate SDD: [medallion-sdd-gates.md](../patterns/medallion-sdd-gates.md) seção Gold.

## Ver também

- [medallion.md](medallion.md) — fronteira de camadas
- [genie-readiness.md](../patterns/genie-readiness.md) — checklist NL/Genie
- [data-lineage.md](data-lineage.md) — `_updated_at`
