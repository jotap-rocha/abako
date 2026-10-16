---
domain: azure-keyvault
description: Azure Key Vault no canônico — facade, map URI/secret name, DefaultAzureCredential (ou equivalente), SI (nunca logar secret); paridade com oci-vault; alinhado a DE-E* sem live API
mcp_validated: null
confidence: null
---

# KB: Azure Key Vault

Base JIT para wiring de secrets no **Azure Key Vault**.
Paridade conceitual com `oci-vault`. Skill: `cloud-secrets`. Pacote **E** (`DE-E*`).
Checks = **filesystem only** — sem API live.

## Capability map

| Pergunta | Onde achar |
|---|---|
| Facade + map URI? | [concepts/facade-and-uri-map.md](concepts/facade-and-uri-map.md) |
| Credential chain? | [concepts/auth-credential-chain.md](concepts/auth-credential-chain.md) |
| Layout greenfield mínimo? | [patterns/greenfield-azure-min.md](patterns/greenfield-azure-min.md) |
| Cheatsheet? | [quick-reference.md](quick-reference.md) |

## Conformidade DE (ponte)

| Âncora | Relação |
|---|---|
| `DE-E001` | Facade `key_azure` / dual presente |
| `DE-E002` | Map só URIs/placeholders |
| `DE-E003` | Consumidores sem `azure.keyvault` |
| `DE-A001` | Literais de secret no código — independente de E |

## SI

- Nunca logar valor de secret.
- Versionar só URI ou `<AZURE_KEYVAULT_SECRET_URI>`.
- Client secrets / connection strings fora do git.

## Learning path

1. `concepts/facade-and-uri-map.md`
2. `concepts/auth-credential-chain.md`
3. Pattern `greenfield-azure-min` + example

## Quick Reference

Ver [quick-reference.md](quick-reference.md).

## Nota

`mcp_validated` / `confidence` = `null` até auditoria Context-7. Alinhado a
`examples/keyvault-azure-min/`.
