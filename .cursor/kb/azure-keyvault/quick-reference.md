---
domain: azure-keyvault
topic: quick-reference
---

# Azure Key Vault — Quick Reference

Ponte: `data-engineering.yaml` (pacote **E**). Sem API live no CI.

### DE-E em uma linha (Azure)

| ID | O que o FS deve ter |
|---|---|
| **DE-E001** | `src/key_azure.py` (ou facade dual) |
| **DE-E002** | `config/secrets_map.yaml` com URI/placeholder |
| **DE-E003** | Pipelines/jobs sem `from azure.keyvault` |

### Marker

```yaml
profile: spark-yarn-airflow   # ou databricks-*
secret_store: azure
```

### Gate

```bash
python -m config.canonical_data_check validate examples/keyvault-azure-min
python -m config.canonical_data_check explain DE-E002
```

### Auth (resumo)

| Contexto | Preferência |
|---|---|
| Laptop / CI | Azure CLI / env de SP — secret fora do git |
| Runtime Azure | `DefaultAzureCredential` / Managed Identity |

### SI

Nunca logar secret. Placeholders only nos examples.
