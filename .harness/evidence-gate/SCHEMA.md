# Schema — evidências / seed `.harness/evidence-gate/`

## Layout (por projeto)

```text
evidencias/
├── tasks/
│   └── <task_id>.yaml      # manifesto atual (LWW)
├── logs/
│   └── <task_id>/
│       └── <criterion_id>.log
└── audit.jsonl             # append-only (G4)
```

No filho via install: seed sob `.harness/evidence-gate/` (SCHEMA + exemplo).
Provas de runtime ficam em `projetos/{slug}/evidencias/` (+ espelho `.cursor`).

## Manifesto `tasks/<task_id>.yaml`

```yaml
task_id: "49"
criteria:
  ac1:
    id: ac1
    command: "python3 -m pytest -q tests/evidence_gate/test_contract.py"
    test_paths:
      - tests/evidence_gate/test_contract.py
    exit_code: 0
    log_path: logs/49/ac1.log
  docs-only:
    id: docs-only
    command: "true"
    test_paths:
    exit_code: 0
    log_path: logs/49/docs-only.log
    waiver:
      human: true
      reason: "critério só documental"
```

- Sem `test_paths` e sem `waiver.human: true` → `check` falha.
- `invalid_cap: true` → prova inválida (log > 2 MiB).

## `audit.jsonl` (append-only)

Uma linha JSON por evento `collect`. Campos estáveis:

| Campo | Tipo | Descrição |
|---|---|---|
| `timestamp` | string ISO-8601 UTC | quando o collect rodou |
| `task_id` | string | id da task |
| `criterion_id` | string | id do critério |
| `exit_code` | int | exit do comando |
| `log_path` | string | path relativo do log |
| `command_summary` | string | comando truncado (sem secret/PII) |
| `collect_ok` | bool | collect considerou ok |
| `invalid_cap` | bool | exceção de cap 2 MiB |

Re-collect **não** apaga linhas anteriores (G4). Manifesto/log atuais = LWW (G2).

## Caps (contrato `evidence-gate.yaml`)

- `limits.max_log_bytes: 2097152` (2 MiB) — fail se exceder
- `limits.collect_time_factor: 2` — alvo; **sem** hard timeout no yaml (G1)
- `seed: true` no stack_map → 1º install COPY; re-install = KEEP

## Ortogonalidade

- Bash deny (`agent-policies`) ≠ aceite mecânico (este kernel)
- `/validar` permanece suite global (ruff+mypy+pytest)
