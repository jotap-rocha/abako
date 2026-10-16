---
name: cloud-secrets
description: >-
  Playbook dual OCI Vault + Azure Key Vault: facade, map só IDs/URIs, auth dual,
  SI (nunca logar secret), ponte JIT para KBs oci-vault e azure-keyvault. Use when:
  "wiring vault", "OCI secrets", "Azure Key Vault", "secret_store", "DE-E001",
  "facade de secrets", "cloud-secrets", "Resource Principal", "DefaultAzureCredential".
---

# cloud-secrets

Skill **dual** (OCI + Azure) para wiring de secrets cloud no Agent Harness.
**Não** cria agent dedicado. Checks normativos: pacote **E** (`DE-E*`) em
`data-engineering.yaml`. Scaffold: `config/templates/cloud-secrets/`.

## Quick start

1. Escolher cofre (grill/define): OCI | Azure | multi — com confirmação humana.
2. Instanciar facade do scaffold → `src/key_oci.py` e/ou `src/key_azure.py`.
3. Map versionado `config/secrets_map.yaml` **só** com OCID/URI/placeholder.
4. Marker: `secret_store: oci|azure|multi` em `.harness/data-check/project_profile.yaml`.
5. Consumidores importam **apenas** o facade — sem SDK vault.
6. Validar: `python -m config.canonical_data_check validate <path>` (pacote E).

## Playbook de wiring

| Peça | OCI | Azure |
|---|---|---|
| Facade | `key_oci.py` | `key_azure.py` |
| Map | OCID `ocid1.vaultsecret...` / `<OCI_VAULT_SECRET_OCID>` | URI `https://….vault.azure.net/secrets/…` / `<AZURE_KEYVAULT_SECRET_URI>` |
| Marker | `secret_store: oci` | `secret_store: azure` |
| Multi | ambos facades + map união + `secret_store: multi` | |

Invariantes:

- Um **ponto único** de integração com o SDK (facade).
- Map **nunca** contém valor de secret — só IDs/URIs.
- `DE-A001` continua banindo literais no código (independente de E).

## Auth dual (orientação)

### OCI

- **Local / CI controlado:** config OCI (`~/.oci/config` ou env) — nunca versionar chave.
- **Runtime cloud (OKE / Instance / Function):** Resource Principal / Instance Principal.
- SDK (`oci.secrets`) **somente** dentro do facade.

### Azure

- **Local:** Azure CLI / env vars de service principal — nunca commit de client secret.
- **Runtime cloud:** `DefaultAzureCredential` (Managed Identity preferencial).
- SDK (`azure.keyvault`) **somente** dentro do facade.

Detalhes JIT: KBs abaixo (não duplique norma longa aqui).

## SI (obrigatório)

- **Nunca** logar valor de secret, token, connection string ou PII.
- Logs: no máximo `ref_present` / nome lógico — nunca o payload.
- Examples e docs: **placeholders only** — sem OCID/credencial real.
- Findings `DE-E*` não devem ecoar valor de secret.

## Gate e remediação

| ID | Intenção |
|---|---|
| `DE-E001` | Facade presente quando vault aplica |
| `DE-E002` | Map só IDs/URIs |
| `DE-E003` | Consumidores sem SDK vault |

Remediação: skill `de-conformidade` + `data-engineering.yaml`.
`/validar` dispara data-check com marker `secret_store` **ou** auto-detect vault.

## KBs (JIT)

- [oci-vault](../../kb/oci-vault/index.md) — auth dual, OCID map, decode, nunca logar
- [azure-keyvault](../../kb/azure-keyvault/index.md) — URI, credential chain, map

## Examples dogfood

- `examples/keyvault-oci-min/` — **sem live API**
- `examples/keyvault-azure-min/` — **sem live API**

Ambos fora do `stack_map`.
