---
topic: unity-catalog-fs-grants-lineage
confidence: null
mcp_validated: null
---

# Unity Catalog FS — grants e lineage (DE-D005)

## Âncora normativa

- **Rule ID:** `DE-D005`
- **Categoria:** `unity-catalog-fs`
- **Fonte:** `data-engineering.yaml` — severidade só no YAML.

## O que resolve

Políticas de **grants** e **linhagem** do Unity Catalog devem existir como arquivos
versionados (YAML / SQL / md). O CI do canônico **não** consulta a UC API — prova é
somente filesystem.

## Artefatos típicos

| Path | Conteúdo |
|---|---|
| `uc/grants.yaml` | Principals → privileges em catalog/schema/table |
| `uc/lineage.md` (ou YAML) | Upstream/downstream documentado |

## O que NÃO fazer

- Assumir que grants no workspace live “contam” para o gate.
- Embeddar tokens de service principal nos YAMLs de grant.
- Logar PII em exemplos de lineage.

## Remediação (ponte)

`remediation` de `DE-D005`: adicione artefatos de grants/linhagem no repo e mantenha-os
atualizados.

## Ver também

- KB: `lakehouse/concepts/metadata-catalogs.md` (UC vs REST vs Glue)
- Examples: `examples/databricks-*/uc/`
- Agents: `lakehouse-architect`, `data-platform-engineer`
