---
domain: oci-vault
topic: facade-and-ocid-map
---

# Facade + map OCID

## Ideia

Todo acesso a secret passa por **um** módulo facade (`key_oci`). O mapa versionado
guarda só **OCID** (ou placeholder) — nunca o valor.

```
consumer → key_oci.get_secret(ocid) → [runtime] OCI Secrets API
config/secrets_map.yaml  →  db_password: ocid1.vaultsecret...
```

## Por quê

- Rotação sem tocar em consumidores.
- Gate `DE-E001`/`E002`/`E003` auditável no FS.
- Evita SDK espalhado (falso positivo de vazamento + acoplamento).

## Anti-padrões

- Importar `oci.secrets` em `pipelines/` ou jobs.
- Colocar password/token literal no YAML do map.
- Logar o retorno de `get_secret`.
