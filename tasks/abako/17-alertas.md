# SPEC-011: alertas R1, R2 e R4

**Status:** not started  
**Blocked by:** tasks/abako/07-saldo-snapshot.md, tasks/abako/15-reserva.md, tasks/abako/16-recorrentes-r2.md

## What to build

Alertas R1 (reserva), R2 (sobra negativa) e R4 (divergência), visíveis na aplicação.

## Acceptance criteria

- [ ] SPEC-011-AC-1: R1 dispara conforme o nível da reserva — tested by: tests/backend/test_alertas.py::test_r1
- [ ] SPEC-011-AC-2: R2 dispara quando a sobra do horizonte é negativa — tested by: tests/backend/test_alertas.py::test_r2
- [ ] SPEC-011-AC-3: R4 aparece na API como condição visível, não só em log — tested by: tests/backend/test_alertas.py::test_r4_visivel

## Notes

Rascunho: os critérios são formalizados em `tests/contracts/criterios.yaml` quando a SPEC for escrita.
