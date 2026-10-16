---
domain: oci-vault
topic: quick-reference
---

# OCI Vault — Quick Reference

Ponte: `data-engineering.yaml` (pacote **E**). Sem API live no CI.

### DE-E em uma linha (OCI)

| ID | O que o FS deve ter |
|---|---|
| **DE-E001** | `src/key_oci.py` (ou facade dual) |
| **DE-E002** | `config/secrets_map.yaml` com OCID/placeholder |
| **DE-E003** | Pipelines/jobs sem `from oci.secrets` |

### Marker

```yaml
profile: spark-yarn-airflow   # ou databricks-*
secret_store: oci
```

### Gate

```bash
python -m config.canonical_data_check validate examples/keyvault-oci-min
python -m config.canonical_data_check explain DE-E001
```

### Auth (resumo)

| Contexto | Preferência |
|---|---|
| Laptop / CI controlado | OCI config / env — chave fora do git |
| Runtime OCI | Resource Principal / Instance Principal |

### SI

Nunca logar secret. Placeholders only nos examples.
