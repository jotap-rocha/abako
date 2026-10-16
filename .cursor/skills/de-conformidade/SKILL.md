---
name: de-conformidade
description: >-
  Interpreta findings do kernel DE (canonical_data_check validate/compare/report/explain),
  mapeia rule_id → remediation do data-engineering.yaml e orienta corrigir código vs
  baseline vs waiver (owner+expiry). Use when: "data-check falhou",
  "DE-A/B/C/D/E finding", "DE-E001", "keyvault-cloud", "como remediar rule_id",
  "baseline ou waiver?", "canonical_data_check explain", "/validar data-check vermelho",
  conformidade spark-yarn, Databricks FS ou vault cloud.
---

# de-conformidade

Playbook único para findings do kernel de engenharia de dados. **Não** inventa bypass;
**não** chama live API; **não** loga secrets/PII.

## Quick start

```bash
# 1) Rodar checks (FS only)
python -m config.canonical_data_check validate <path>

# 2) Relatório / explicar um ID
python -m config.canonical_data_check report <path>
python -m config.canonical_data_check explain <rule_id>

# 3) Decidir: corrigir | baseline | waiver — ver workflow abaixo
```

No filho com marker DE, auto-detect SDP/DLT **ou** vault (`secret_store` / auto-detect),
`/validar` já dispara o validate.

## Workflow

### 1. Coletar findings

1. Rode `validate <path>` (e `report` se precisar de visão agregada).
2. Anote cada `rule_id`, path e severidade.
3. Para um ID: `explain <rule_id>` — puxa título/explanation/remediation do YAML.

### 2. Mapear rule_id → remediation

- Fonte única: `data-engineering.yaml` (pacotes A–E).
- Tabela-ponte curta: [references/rule-ids-remediation.md](references/rule-ids-remediation.md).
- **Nunca** inventar remediação diferente do YAML; se o YAML mudar, o YAML vence.

### 3. Decidir: corrigir vs baseline vs waiver

| Opção | Quando | Como |
|---|---|---|
| **Corrigir** | Default — dívida real no código/config | Aplicar `remediation` do YAML; re-`validate` |
| **Baseline** | Brownfield: finding **já conhecido**, ratchet | `python -m config.canonical_data_check baseline <path>` → `.harness/data-check/baseline.json` |
| **Waiver** | Exceção **temporária** documentada | Entrada em `waivers.yaml` com **owner** + **expiry** obrigatórios |

Detalhes e schema: [references/baseline-waiver.md](references/baseline-waiver.md).

Ordem ética:

1. Preferir **corrigir**.
2. **Baseline** só para congelar o conhecido (não esconde finding *novo* no `compare`).
3. **Waiver** com owner+expiry; expirado/incompleto **não** silencia.

### 4. Revalidar

```bash
python -m config.canonical_data_check validate <path>
python -m config.canonical_data_check compare <path>   # se usa ratchet
```

Finding novo vs baseline (sem waiver válido) → falha. Status `baseline` / `waived` no compare
não quebram o ratchet para o conhecido.

## SI (obrigatório)

- Nunca logar secrets, tokens, connection strings ou PII.
- Baseline persiste fingerprints sanitizados (sem `message` com dado sensível).
- Não sugerir `--no-verify`, apagar checks, ou fake green.
- Produção permanece somente-leitura salvo ADR + aprovação humana.

## Databricks (pacote D)

IDs `DE-D001`…`DE-D005` → KB `kb/databricks/` (conceitos 1:1). Checks são **FS only**.

## Key Vault / cloud secrets (pacote E)

IDs `DE-E001`…`DE-E003` → skill `cloud-secrets` + KBs `oci-vault` / `azure-keyvault`.
Applicability: marker `secret_store` **ou** auto-detect; `multi` = união. Checks **FS only**
(sem API live). `DE-A001` permanece independente (literais no código).

| ID | Remediação (resumo — YAML vence) |
|---|---|
| `DE-E001` | Criar facade (`key_oci` / `key_azure` / dual) — scaffold `config/templates/cloud-secrets/` |
| `DE-E002` | Map só OCID/URI/placeholder — nunca valor |
| `DE-E003` | Remover SDK vault dos consumidores; usar o facade |

## Agents

Qualquer agent DE com seção Kernel pode apontar esta skill após finding do gate.
