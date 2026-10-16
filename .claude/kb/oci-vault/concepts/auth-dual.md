---
domain: oci-vault
topic: auth-dual
---

# Auth dual — local vs Resource Principal

## Local / CI

- Usar config OCI ou variáveis de ambiente.
- **Nunca** versionar chave PEM ou passphrase.
- Facade lê config; consumidores não conhecem o mecanismo.

## Runtime cloud (OCI)

- Preferir **Resource Principal** (ou Instance Principal) no workload.
- Mesma assinatura de facade — só a construção do client muda.

## Regra

SDK OCI Vault **somente** dentro do facade. Fora = violação `DE-E003`.
