---
topic: schema-rescue
confidence: null
mcp_validated: null
---

# Schema rescue policy (DE-D004)

## Âncora normativa

- **Rule ID:** `DE-D004`
- **Categoria:** `schema-rescue`
- **Fonte:** `data-engineering.yaml` — **não** duplicar severidade.

## O que resolve

Drift de schema em cloud exige política explícita (**fail** vs **quarantine**) no
repositório, auditável **sem** workspace live. O check valida presença/conteúdo da
policy no FS, não o comportamento runtime do cluster.

## Artefato típico

```yaml
# config/schema-rescue-policy.yaml (ilustrativo)
schema_rescue:
  on_drift: fail   # ou quarantine
  documented_by: data-platform
```

Aplique a policy tanto em perfis SDP quanto DLT (applicability `databricks-cloud`).

## Relação com modelagem

- Evolução de schema em open table formats → KB `lakehouse/concepts/schema-evolution.md`.
- Grão / contratos → `data-modeling/` e `data-quality/`.
- Este concept cobre só a **policy de rescue** exigida por DE-D004.

## Remediação (ponte)

`remediation` de `DE-D004`: versionar a policy e referenciá-la no pipeline.

## Ver também

- Examples: `examples/databricks-sdp-min/config/schema-rescue-policy.yaml`
- Agents: `schema-designer`, `data-quality-analyst`
