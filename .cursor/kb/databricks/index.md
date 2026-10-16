---
domain: databricks
description: Databricks no canônico — DAB/bundle, SDP medallion, DLT quarentena/expectations, schema rescue e Unity Catalog FS (grants+lineage); alinhado a DE-D001–005 sem live API
mcp_validated: null
confidence: null
---

# KB: Databricks (pacote D — FS only)

Base de conhecimento **específica de Databricks** no Agent Harness Canônico.
Complementa `lakehouse/` (agnóstico de vendor) e `cloud-platforms/` (comparativo).
Escopo: artefatos **versionados no filesystem** — o CI do canônico **não** consulta
live API do workspace.

Fonte normativa de severidade e remediação: `data-engineering.yaml` (pacote **D**).
Este KB **não** duplica severidade.

## Capability map

| Pergunta | Onde achar |
|---|---|
| Bundle/job com identidade de execução? | [concepts/dab-bundle-identity.md](concepts/dab-bundle-identity.md) |
| Pipeline SDP com camadas medallion? | [concepts/sdp-medallion.md](concepts/sdp-medallion.md) |
| DLT com expectations + quarentena? | [concepts/dlt-quarantine-expectations.md](concepts/dlt-quarantine-expectations.md) |
| Política de schema rescue (fail vs quarantine)? | [concepts/schema-rescue.md](concepts/schema-rescue.md) |
| Grants/linhagem UC no repositório? | [concepts/unity-catalog-fs-grants-lineage.md](concepts/unity-catalog-fs-grants-lineage.md) |
| Greenfield estilo `databricks-sdp-min`? | [patterns/greenfield-sdp-min.md](patterns/greenfield-sdp-min.md) |
| Quarentena DLT mínima? | [patterns/dlt-quarantine.md](patterns/dlt-quarantine.md) |
| Identidade DAB auditável? | [patterns/dab-identity.md](patterns/dab-identity.md) |
| Pré-requisito AI-DEV-KIT (gate SDD Databricks)? | [patterns/ai-dev-kit-gate.md](patterns/ai-dev-kit-gate.md) |

## Conceitos (1:1 com DE-D00n)

| Arquivo | Rule ID |
|---|---|
| [dab-bundle-identity.md](concepts/dab-bundle-identity.md) | **DE-D001** |
| [sdp-medallion.md](concepts/sdp-medallion.md) | **DE-D002** |
| [dlt-quarantine-expectations.md](concepts/dlt-quarantine-expectations.md) | **DE-D003** |
| [schema-rescue.md](concepts/schema-rescue.md) | **DE-D004** |
| [unity-catalog-fs-grants-lineage.md](concepts/unity-catalog-fs-grants-lineage.md) | **DE-D005** |

## Padrões

| Arquivo | Uso |
|---|---|
| [greenfield-sdp-min.md](patterns/greenfield-sdp-min.md) | Layout mínimo SDP + D (example canônico) |
| [dlt-quarantine.md](patterns/dlt-quarantine.md) | Expectations + destino de quarentena |
| [dab-identity.md](patterns/dab-identity.md) | `owner` / `run_as` no bundle |
| [ai-dev-kit-gate.md](patterns/ai-dev-kit-gate.md) | Pré-requisito SDD Databricks (gate humano) |

## Conformidade DE (ponte)

Fonte: `data-engineering.yaml` — este KB **não** duplica severidade nem texto normativo longo.

| Âncora | Relação |
|---|---|
| `DE-D001` | DAB/layout + identidade de execução |
| `DE-D002` | SDP medallion (bronze/silver/gold) |
| `DE-D003` | DLT quarentena / expectations |
| `DE-D004` | Schema rescue policy |
| `DE-D005` | Unity Catalog grants + lineage em FS |
| pacote **D** | checks filesystem; **sem API live** |

Gate: `python -m config.canonical_data_check validate <path>` · `/validar` quando marker
ou auto-detect SDP/DLT. Skill: `de-conformidade`.

## Agents sugeridos

`lakehouse-architect`, `data-platform-engineer`, `data-quality-analyst`, `schema-designer`
(+ `spark-engineer` para stubs PySpark/SDP).

## Learning path

1. `concepts/dab-bundle-identity.md` (DE-D001) — identidade auditável.
2. Escolha o motor: SDP (`sdp-medallion`) ou DLT (`dlt-quarantine-expectations`).
3. Feche `schema-rescue` + `unity-catalog-fs-grants-lineage`.
4. Patterns sob demanda; valide no example `examples/databricks-*-min/`.

## Quick Reference

Ver [quick-reference.md](quick-reference.md).

## Nota de validação

`mcp_validated` / `confidence` = `null` até auditoria Context-7. Conteúdo alinhado aos
checks do pacote D e aos examples estáticos do canônico.
