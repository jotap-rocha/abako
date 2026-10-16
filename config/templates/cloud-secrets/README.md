# Scaffold — cloud-secrets (facade dual)

Template canônico para wiring de secrets cloud (OCI Vault / Azure Key Vault).
Os examples `examples/keyvault-oci-min/` e `examples/keyvault-azure-min/` **instanciam**
estes stubs — não forkam lógica.

## Conteúdo

| Arquivo | Papel |
|---|---|
| `key_oci.py` | Facade OCI (ponto único) |
| `key_azure.py` | Facade Azure (ponto único) |
| `secrets_map.oci.yaml` | Map só OCIDs / placeholders |
| `secrets_map.azure.yaml` | Map só URIs / placeholders |
| `consumer_stub.py` | Consumidor que usa o facade (sem SDK vault) |

## Regras (pacote E)

- **DE-E001** — facade presente (`key_oci` / `key_azure` / dual)
- **DE-E002** — map só IDs/URIs (nunca valor de secret)
- **DE-E003** — consumidores sem `oci.secrets` / `azure.keyvault`

## Uso

1. Copie o facade adequado para `src/` do projeto.
2. Copie o map correspondente para `config/secrets_map.yaml`.
3. Declare `secret_store: oci|azure|multi` no marker `.harness/data-check/project_profile.yaml`.
4. Consumidores importam só o facade.

**Sem live API** no CI do canônico — stubs levantam `NotImplementedError` se chamados.
