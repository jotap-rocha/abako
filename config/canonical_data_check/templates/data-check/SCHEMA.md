# Schema — `.harness/data-check/` (runtime no projeto-filho)

Templates seed no canônico (consumidos pelo install mínimo — Task 15):

`config/canonical_data_check/templates/data-check/`

## Layout no projeto-alvo

```text
.harness/data-check/
├── project_profile.yaml   # perfil normativo (ex.: spark-yarn-airflow)
├── baseline.json          # snapshot ratchet dos blockers conhecidos
└── waivers.yaml           # exceções pontuais (owner + expiry)
```

## `project_profile.yaml`

```yaml
profile: spark-yarn-airflow
# secret_store: oci   # opcional — oci | azure | multi (override do auto-detect vault)
```

| Campo | Tipo | Descrição |
|---|---|---|
| `profile` | string | Perfil normativo DE (ex.: `spark-yarn-airflow`, `databricks-sdp-medallion`) |
| `secret_store` | string\|omitido | Override ortogonal: `oci` \| `azure` \| `multi`. Vence auto-detect de vault; ausente/inválido → detector FS |

O pacote **E** (`keyvault-cloud`, `DE-E*`) é injetado pelo engine quando
`secret_store` aplica (marker **ou** auto-detect). Não precisa constar em
`profiles.*.packages` do `data-engineering.yaml`.

## `baseline.json`

| Campo | Tipo | Descrição |
|---|---|---|
| `version` | int | Schema version (atual: `1`) |
| `profile` | string | Perfil efetivo usado na geração; mantido para compatibilidade com consumidores Loop 1 |
| `profiles` | array<string> | Opcional; perfis cloud efetivos em ordem lexicográfica. Em `databricks-multi`, contém os componentes DLT e SDP |
| `generated_at` | string\|null | ISO-8601 UTC da última gravação |
| `findings` | array | Entradas sanitizadas (sem `message` / sem secrets) |

Baselines legados somente com `profile` continuam válidos no `compare`. O seed
`spark-yarn-airflow` permanece singular; `profiles[]` é gravado pelo comando
`baseline` quando o perfil efetivo é cloud ou `databricks-multi`.

Cada finding:

| Campo | Tipo | Descrição |
|---|---|---|
| `rule_id` | string | ID normativo (ex.: `DE-B003`) |
| `path` | string | Path relativo (pode incluir `:linha`) |
| `severity` | string | Severidade (blocker) |
| `fingerprint` | string | `rule_id\|path` — path **sem** sufixo `:linha` (ratchet estável a shift de linha) |

**SI:** nunca persistir valor de secret; a CLI omite `message` no snapshot.

**Ratchet:** finding novo (fingerprint ausente no baseline) falha; finding conhecido → status `baseline`.

## `waivers.yaml`

```yaml
waivers:
  - rule_id: DE-A001
    owner: data-platform
    expiry: "2026-12-31"
    reason: exceção temporária documentada
```

Regras:

- `owner` e `expiry` são **obrigatórios** para silenciar blocker.
- `expiry` no passado → waiver inativo (comparado em data UTC).
- Waiver incompleto → **não** silencia (blocker permanece `fail`).
- Waiver ativo → finding com status `waived` no `compare`.
- Escopo Loop 1: waiver por **`rule_id`** (silencia todos os findings daquele ID).
  Path/fingerprint opcional fica para evolução futura (auditoria pontual).

## CLI

```bash
python -m config.canonical_data_check baseline <path>
python -m config.canonical_data_check compare <path>
```

- `baseline`: grava snapshot idempotente/atômico; exit `0` se a escrita ok.
- `compare`: falha (`1`) só em finding **novo** vs baseline (e sem waiver válido).
- `baseline.json` existente porém ilegível/corrompido → exit `2` (`DE-USAGE`); não trata como baseline vazio.

## Nota

Não gravar baseline no brownfield RO `data-sql-capacity-evolution-prd` neste ship.
