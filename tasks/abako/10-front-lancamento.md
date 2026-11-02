# SPEC-012 (3/5): formulário de lançamento

**Status:** not started  
**Blocked by:** tasks/abako/08-front-saldos.md, tasks/abako/09-lancamento.md

## What to build

Formulário de lançamento com campos que mudam por tipo, edição com histórico de versões, exclusão e envio com a mesma chave de idempotência em retry.

## Acceptance criteria

- [ ] SPEC-012-AC-7: os campos do formulário mudam conforme o tipo — tested by: frontend/src/lancamento/Formulario.test.tsx::campos_por_tipo
- [ ] SPEC-012-AC-8: erro de validação aparece em linguagem direta, sem retry cego de escrita — tested by: frontend/src/lancamento/Erros.test.tsx::erro_direto
- [ ] SPEC-012-AC-9: jornada lançar e ver o saldo mudar — tested by: tests/e2e/test_lancamento.py::test_lancar_e_ver_saldo

## Notes

Rascunho: os critérios são formalizados em `tests/contracts/criterios.yaml` quando a SPEC for escrita.
