---
domain: azure-keyvault
topic: greenfield-azure-min
---

# Pattern — greenfield Azure min

Espelha `examples/keyvault-azure-min/` + scaffold `config/templates/cloud-secrets/`.

1. Copiar `key_azure.py` → `src/key_azure.py`
2. Copiar `secrets_map.azure.yaml` → `config/secrets_map.yaml`
3. Marker `secret_store: azure`
4. Consumidor importa só o facade
5. `validate` deve PASS sem live API

Skill: `cloud-secrets`.
