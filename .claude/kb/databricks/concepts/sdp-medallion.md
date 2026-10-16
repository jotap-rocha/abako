---
topic: sdp-medallion
confidence: null
mcp_validated: null
---

# SDP medallion (DE-D002)

## Âncora normativa

- **Rule ID:** `DE-D002`
- **Categoria:** `sdp-medallion`
- **Fonte:** `data-engineering.yaml` — **não** duplicar severidade aqui.

## O que resolve

Quando há **sinal SDP** no repositório (ex. `pyspark.pipelines`, decorators `@dp.`), o
pipeline deve declarar camadas **medallion** (bronze / silver / gold ou equivalente) de
forma explícita — paths, contratos e direção do fluxo auditáveis no FS.

## Sinais no filesystem

- Código SDP em `pipelines/` (import / decorator reconhecido pelo detector).
- `config/layers.yaml` (ou equivalente) listando camadas e direção permitida.
- Perfil efetivo típico: `databricks-sdp-medallion` (auto-detect ou marker).

## Relação com outros IDs

| ID | Quando |
|---|---|
| DE-D001 | Bundle sempre (identidade) |
| DE-D003 | Skip se **não** há sinal DLT |
| DE-D004 / D005 | Schema rescue + UC FS |

## Remediação (ponte)

`remediation` de `DE-D002` no YAML: declare camadas SDP, contratos e direção do fluxo.

## Ver também

- Pattern: [greenfield-sdp-min.md](../patterns/greenfield-sdp-min.md)
- KB adjacente: `lakehouse/` (formatos) · `pipeline/concepts/medallion.md` (conceito geral)
- Example: `examples/databricks-sdp-min/config/layers.yaml`
