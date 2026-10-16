---
domain: azure-keyvault
topic: auth-credential-chain
---

# Auth — DefaultAzureCredential (ou equivalente)

## Local / CI

- Azure CLI logado ou variáveis de service principal.
- **Nunca** versionar `client_secret` / connection string.

## Runtime Azure

- Preferir **Managed Identity** via `DefaultAzureCredential` (ou cadeia documentada
  equivalente no stack do time).
- Facade encapsula a credential; consumidores não veem o mecanismo.

## Regra

SDK Azure Key Vault **somente** dentro do facade. Fora = `DE-E003`.
