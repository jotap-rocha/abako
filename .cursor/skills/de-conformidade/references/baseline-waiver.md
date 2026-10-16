# Baseline e waiver

Schema canônico: `config/canonical_data_check/templates/data-check/SCHEMA.md`
(seed → `.harness/data-check/` no filho; `seed: true` = KEEP no re-install).

## Layout

```text
.harness/data-check/
├── project_profile.yaml   # opcional / override de perfil
├── baseline.json          # ratchet de findings conhecidos
└── waivers.yaml           # exceções com owner + expiry
```

## Baseline

```bash
python -m config.canonical_data_check baseline <path>
python -m config.canonical_data_check compare <path>
```

- **baseline:** grava snapshot sanitizado (sem `message`/secrets); cloud/multi pode
  persistir `profiles[]`.
- **compare:** falha só em finding **novo** (fingerprint ausente) sem waiver ativo.
- Finding no baseline → status `baseline` (não quebra o ratchet).
- `baseline.json` corrompido → exit `2` (`DE-USAGE`); não trate como vazio.

Use baseline para brownfield honesto — não para esconder regressão nova.

## Waiver

```yaml
waivers:
  - rule_id: DE-D003
    owner: data-platform
    expiry: "2026-12-31"
    reason: migração DLT em andamento — quarentena na sprint N+1
```

Regras:

- `owner` e `expiry` **obrigatórios** para silenciar.
- `expiry` no passado (UTC) → inativo.
- Incompleto → **não** silencia (blocker permanece).
- Escopo atual: waiver por `rule_id` (todos os findings daquele ID).

## Decisão rápida

```
Finding aparece no validate?
  ├── Posso corrigir agora? → CORRIGIR (preferencial)
  ├── É dívida já conhecida no ratchet? → baseline + compare
  └── Exceção temporária acordada? → waiver (owner+expiry) + ticket/ADR se sensível
```

## SI

- Não gravar PII/secrets em `reason`, logs ou fingerprints.
- Não usar waiver eterno sem expiry.
- Produção: sem DDL destrutivo sem ADR + aprovação humana.
