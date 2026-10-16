# Ponte rule_id → remediation

Fonte normativa: **`data-engineering.yaml`** na raiz do canônico.
Este arquivo é índice curto — **não** copia severidades nem textos longos.

## Como usar

1. Obtenha o `rule_id` do finding (`validate` / `report`).
2. Rode `python -m config.canonical_data_check explain <rule_id>`.
3. Aplique o campo `remediation` retornado / declarado no YAML.
4. Se precisar de contexto de domínio Databricks: `kb/databricks/` (DE-D*).

## Pacotes (âncoras)

| Prefixo | Pacote | Exemplos de categoria |
|---|---|---|
| `DE-A*` | Universal | ownership, logging, run_id, contratos mínimos |
| `DE-B*` | Spark/YARN | layout jobs, configs de execução |
| `DE-C*` | Airflow | DAG/TaskFlow (quando aplicável) |
| `DE-D*` | Databricks cloud FS | DAB, SDP, DLT, schema rescue, UC FS |
| `DE-E*` | Key Vault cloud | facade, map IDs/URIs, consumidores sem SDK |

## DE-B003 — contrato + Silver checklist

| ID | Categoria | Remediação (resumo — YAML vence) |
|---|---|---|
| DE-B003 | data-contract | Contrato versionado (schema, tipos, versão) |

Após cumprir `DE-B003`, implemente regras Silver prescritivas mapeadas ao contrato ODCS:
`kb/pipeline/patterns/silver-checklist-odcs.md` (dedup, limpeza, validação, severidade
`fail` \| `quarantine` \| `log`). Ponte conceitual: `kb/pipeline/concepts/data-contracts.md`
§ Integração Silver.

## DE-D001…005 (ponte Databricks)

| ID | Categoria | Remediação (resumo — YAML vence) |
|---|---|---|
| DE-D001 | dab-layout | Bundle/job YAML + owner/run identity versionados |
| DE-D002 | sdp-medallion | Declarar camadas SDP + direção do fluxo |
| DE-D003 | dlt-quarantine | Política + destino de quarentena no DLT |
| DE-D004 | schema-rescue | Versionar policy fail vs quarantine |
| DE-D005 | unity-catalog-fs | Artefatos grants/lineage no FS |

## DE-E001…003 (ponte keyvault-cloud)

| ID | Categoria | Remediação (resumo — YAML vence) |
|---|---|---|
| DE-E001 | secret-facade | Facade versionado (`key_oci` / `key_azure` / dual) |
| DE-E002 | secret-map | Map só OCID/URI/placeholder — sem valor |
| DE-E003 | secret-consumers | Sem SDK vault fora do facade |

Domínio JIT: `kb/oci-vault/` · `kb/azure-keyvault/` · skill `cloud-secrets`.
Para A/B/C: sempre `explain <rule_id>` — não manter cópia paralela aqui.

## Anti-padrões

- Duplicar severidade (`blocker`/`warn`) em docs de agente.
- Inventar workaround que desliga o check.
- Colocar secrets na mensagem de remediação ou no commit.
