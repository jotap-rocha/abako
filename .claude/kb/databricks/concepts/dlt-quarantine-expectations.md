---
topic: dlt-quarantine-expectations
confidence: null
mcp_validated: null
---

# DLT — expectations e quarentena (DE-D003)

## Âncora normativa

- **Rule ID:** `DE-D003`
- **Categoria:** `dlt-quarantine`
- **Fonte:** `data-engineering.yaml` — severidade só no YAML.

## O que resolve

Pipelines **DLT** com expectations precisam de **destino de quarentena versionado** para
registros que falham qualidade. Expectation sem quarentena documentada = finding no
pacote D (quando o sinal DLT está presente).

## Sinais no filesystem

- Código com `import dlt` / `@dlt.` e expectations.
- `config/quarantine-policy.yaml` (ou equivalente) com tabela/destino e política
  (`on_expectation_fail: quarantine`, etc.).
- Perfil típico: `databricks-dlt-legacy`.

## Expectations vs quarentena

| Peça | Papel |
|---|---|
| Expectation | Regra de qualidade no pipeline |
| Quarentena | Destino FS-documentado para inválidos |
| Notificação | Fora do escopo mínimo do check D003 |

## Remediação (ponte)

`remediation` de `DE-D003`: declare a política e o destino de quarentena no pipeline DLT.

## Ver também

- Pattern: [dlt-quarantine.md](../patterns/dlt-quarantine.md)
- KB: `data-quality/` (dimensões) · `pipeline/concepts/quarantine.md`
- Example: `examples/databricks-dlt-min/`
