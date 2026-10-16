---
domain: oci-vault
topic: greenfield-oci-min
---

# Pattern — greenfield OCI min

Espelha `examples/keyvault-oci-min/` + scaffold `config/templates/cloud-secrets/`.

1. Copiar `key_oci.py` → `src/key_oci.py`
2. Copiar `secrets_map.oci.yaml` → `config/secrets_map.yaml`
3. Marker `secret_store: oci`
4. Consumidor importa só o facade
5. `validate` deve PASS sem live API

Skill: `cloud-secrets`.
