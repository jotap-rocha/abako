---
domain: oci-vault
description: OCI Vault no canônico — facade, map OCID, auth dual (config local vs Resource Principal), decode e SI (nunca logar secret); alinhado a DE-E* sem live API
mcp_validated: null
confidence: null
---

# KB: OCI Vault

Base JIT para wiring de secrets no **Oracle Cloud Infrastructure Vault**.
Complementa a skill `cloud-secrets` e o pacote **E** (`DE-E001`–`E003`).
Checks do canônico são **filesystem only** — sem API live.

## Capability map

| Pergunta | Onde achar |
|---|---|
| Por que facade + map OCID? | [concepts/facade-and-ocid-map.md](concepts/facade-and-ocid-map.md) |
| Auth local vs cloud? | [concepts/auth-dual.md](concepts/auth-dual.md) |
| Layout greenfield mínimo? | [patterns/greenfield-oci-min.md](patterns/greenfield-oci-min.md) |
| Cheatsheet? | [quick-reference.md](quick-reference.md) |

## Conformidade DE (ponte)

| Âncora | Relação |
|---|---|
| `DE-E001` | Facade `key_oci` / dual presente |
| `DE-E002` | Map só OCIDs/placeholders |
| `DE-E003` | Consumidores sem `oci.secrets` |
| `DE-A001` | Literais de secret no código — independente de E |

Fonte normativa: `data-engineering.yaml`. Este KB **não** duplica severidade.

## SI

- Nunca logar valor de secret / bundle decodificado.
- Versionar só OCID ou `<OCI_VAULT_SECRET_OCID>`.
- Chaves de API e PEM ficam fora do git (secret manager / env).

## Learning path

1. `concepts/facade-and-ocid-map.md`
2. `concepts/auth-dual.md`
3. Pattern `greenfield-oci-min` + validate no example

## Quick Reference

Ver [quick-reference.md](quick-reference.md).

## Nota

`mcp_validated` / `confidence` = `null` até auditoria Context-7. Conteúdo alinhado aos
checks E e ao example `examples/keyvault-oci-min/`.
