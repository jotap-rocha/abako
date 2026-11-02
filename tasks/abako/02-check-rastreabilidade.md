# SPEC-001b: check, rastreabilidade e CI

**Status:** not started  
**Blocked by:** tasks/abako/01-ambiente-banco.md

## What to build

Comando único `check` (lint, tipos, testes e rastreabilidade), script de rastreabilidade que lista invariantes e critérios sem teste (deve retornar vazio) e CI completo (Vitest, Playwright, Postgres efêmero) conforme `03-harness.md`. Versões exatas das dependências de frontend fixadas.

## Acceptance criteria

- [ ] SPEC-001-AC-4: `check` roda lint, tipos, testes e rastreabilidade e falha se qualquer etapa falhar — tested by: tests/test_check.py::test_check_falha_quando_etapa_falha
- [ ] SPEC-001-AC-5: o script de rastreabilidade lista invariantes/critérios sem teste e retorna vazio quando tudo tem teste — tested by: tests/test_rastreabilidade.py::test_lista_sem_teste
- [ ] SPEC-001-AC-6: o CI executa o `check` completo sem segredos — no test automático — verificado no primeiro run do workflow; waiver humano com o link do run

## Notes

Branch protection exige os checks depois do primeiro run.
