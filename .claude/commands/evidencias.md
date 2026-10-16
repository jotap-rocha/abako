# /evidencias — atalho do evidence-gate

Prova mecânica de aceite **por task** (manifesto + logs + audit).

## Uso

```bash
python -m config.evidence_gate check --contract
python -m config.evidence_gate collect --root <evidencias/> --task NN --criterion <id> --command "..."
python -m config.evidence_gate check --root <evidencias/> --task NN --entregas metrics/entregas.jsonl --issue NN
```

Cheatsheet: `docs/cheatsheets/evidence-gate-cheatsheet.md`  
Contrato: `evidence-gate.yaml`  
Seed filho: `.harness/evidence-gate/`

**Não** substitui `/validar`. **Não** misturar com `agent-policies` (Bash deny ≠ aceite).
Honesty §1.3: gate local; manifesto forjável sem Edit policies.
