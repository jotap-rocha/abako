---
domain: databricks
topic: quick-reference
---

# Databricks — Quick Reference

Ponte normativa: `data-engineering.yaml` (pacote **D**). Severidades **não** se
duplicam aqui. Checks = filesystem only — **sem API live**.

### DE-D001…005 em uma linha

| ID | O que o FS deve ter |
|---|---|
| **DE-D001** | `databricks.yml` / bundle com `owner` ou `run_as` auditável |
| **DE-D002** | Camadas medallion explícitas (bronze/silver/gold) se sinal SDP |
| **DE-D003** | Destino/política de quarentena se sinal DLT + expectations |
| **DE-D004** | Policy de schema rescue (fail vs quarantine) versionada |
| **DE-D005** | Grants + lineage UC em arquivos (YAML/SQL/md) |

### Gate local

```bash
python -m config.canonical_data_check validate examples/databricks-sdp-min
python -m config.canonical_data_check validate examples/databricks-dlt-min
python -m config.canonical_data_check report <path>
python -m config.canonical_data_check explain <rule_id>
```

### Layout mínimo (sdp-min)

| Path | ID |
|---|---|
| `databricks.yml` | D001 |
| `config/layers.yaml` | D002 |
| `config/schema-rescue-policy.yaml` | D004 |
| `uc/grants.yaml` + `uc/lineage.md` | D005 |
| `pipelines/*_sdp.py` | sinal SDP |

### Layout mínimo (dlt-min)

| Path | ID |
|---|---|
| `databricks.yml` | D001 |
| `config/quarantine-policy.yaml` | D003 |
| `config/schema-rescue-policy.yaml` | D004 |
| `uc/grants.yaml` + `uc/lineage.md` | D005 |
| `pipelines/*_dlt.py` | sinal DLT |

### Decision tree: SDP vs DLT

```
Novo pipeline Databricks no canônico?
  ├── Declarativo/medallion greenfield → perfil SDP (D002; D003 skip)
  └── Legacy DLT + expectations → perfil DLT (D003; D002 skip)
Sempre: D001 + D004 + D005 no FS
```

### SI

- Sem tokens/PAT no repo; secrets só via env/secret manager.
- Sem PII em logs dos stubs; examples sem dados pessoais.
- Não inventar bypass de check — use skill `de-conformidade` (corrigir / baseline / waiver).

### Examples canônicos

- `examples/databricks-sdp-min/`
- `examples/databricks-dlt-min/`
