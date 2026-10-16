# Evidence-gate — cheatsheet (1 página)

Kernel de **prova mecânica de aceite por task**. Ortogonal a `/validar` (suite global) e a
`agent-policies` (freio Bash). Soft review (`revisor-codigo`) **não** substitui este gate.

## CLI

```bash
python -m config.evidence_gate check --contract
python -m config.evidence_gate collect \
  --root .claude/projetos/{slug}/evidencias \
  --task NN --criterion ac1 \
  --command "python3 -m pytest -q path/to/test.py" \
  --test-path path/to/test.py
python -m config.evidence_gate check \
  --root .claude/projetos/{slug}/evidencias \
  --task NN --entregas metrics/entregas.jsonl --issue NN
```

Helper de close: `config.evidence_gate.close.close_task_evidence_gate` /
`append_entrega_with_ref` (exige `evidencias_ref`).

## Artefatos

| Path | Papel |
|---|---|
| `evidence-gate.yaml` | Contrato (cap 2 MiB, fator 2×, regras check) |
| `evidencias/tasks/<id>.yaml` | Manifesto atual (LWW) |
| `evidencias/logs/<id>/<crit>.log` | Saída do collect |
| `evidencias/audit.jsonl` | Histórico append-only |
| `metrics/entregas.jsonl` | Delivery + `evidencias_ref` |

## Caps / concorrência

- Log > **2 MiB** → collect **falha** (sem prova truncada)
- Alvo collect ≤ **2×** comando — **sem** hard timeout no yaml
- Prova atual = **LWW**; audit = **append-only**

## Waiver

Sem teste só com `waiver: { human: true, reason: "..." }` no critério.

## Ortogonalidade (não unificar)

- **Bash deny ≠ aceite** (`agent-policies` freia shell; evidence-gate prova critério)
- **`/validar` permanece** (ruff+mypy+pytest + DE condicional)
- Revisor = soft; evidence-gate = hard

## Honesty §1.3

Gate **local**. Manifesto pode ser forjado à mão; sem Edit policies / branch protection
nenhum freio impede de fato. Melhor dogfood auditável — não bloqueio server-side.

Ver: `docs/adr/004-kernel-evidence-gate.md` · seed `.harness/evidence-gate/` · command `/evidencias`.
