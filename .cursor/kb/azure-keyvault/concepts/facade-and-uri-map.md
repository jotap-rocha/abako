---
domain: azure-keyvault
topic: facade-and-uri-map
---

# Facade + map URI

## Ideia

Todo acesso passa por **um** facade (`key_azure`). O mapa versionado guarda só
**URI** (ou nome + vault URL / placeholder) — nunca o valor.

```
consumer → key_azure.get_secret(uri_or_name) → [runtime] Key Vault API
config/secrets_map.yaml  →  db_password: https://….vault.azure.net/secrets/…
```

## Paridade OCI

Mesmo desenho que `oci-vault` (facade + map + DE-E*). Só muda o identificador
(URI vs OCID) e o SDK dentro do facade.

## Anti-padrões

- Importar `azure.keyvault` fora do facade.
- Literal de password no YAML.
- Logar o retorno de `get_secret`.
