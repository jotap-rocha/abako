---
topic: dab-identity
confidence: null
mcp_validated: null
---

# Pattern: identidade DAB auditável

## Quando usar

Qualquer projeto com `databricks.yml` / bundle no canônico — fechar **DE-D001**.

## Manifesto mínimo (ilustrativo)

```yaml
bundle:
  name: orders-sdp-min

run_as:
  service_principal_name: sp-orders-sdp-runner

owner: data-platform
```

- `owner`: time/humano responsável (auditável no git).
- `run_as.service_principal_name`: identidade de execução — **nome**, não token.
- Nunca coloque PAT / client secret neste arquivo.

## Checklist

- [ ] Bundle versionado na raiz (ou path reconhecido pelo check).
- [ ] `owner` **ou** `run_as` presente e legível.
- [ ] Sem secrets hardcoded; secrets só em env/secret manager.
- [ ] `validate` local passa DE-D001.

## Remediação

Se `explain DE-D001` / finding apontar layout: adicione o YAML e declare identidade —
texto canônico em `data-engineering.yaml` → `remediation`.

## Ver também

- Concept: [dab-bundle-identity.md](../concepts/dab-bundle-identity.md)
- Examples: `examples/databricks-sdp-min/databricks.yml`, `examples/databricks-dlt-min/databricks.yml`
