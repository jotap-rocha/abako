# SPEC-001c: esquema base e garantias

**Status:** not started  
**Blocked by:** tasks/abako/02-check-rastreabilidade.md

## What to build

Esquema base do ledger: `user_id` em toda tabela, papéis do banco (aplicação sem UPDATE/DELETE nas tabelas de versão), versão vigente única, campo de versão para controle otimista, chave de idempotência, flag de conta de benefício, `NUMERIC` para dinheiro.

## Acceptance criteria

- [ ] SPEC-001-AC-7: toda tabela tem `user_id` (INV-13) — tested by: tests/db/test_esquema.py::test_toda_tabela_tem_user_id
- [ ] SPEC-001-AC-8: inserir segunda versão vigente da mesma entidade falha (INV-27) — tested by: tests/db/test_versao_vigente.py::test_segunda_vigente_falha
- [ ] SPEC-001-AC-9: o papel da aplicação não tem UPDATE/DELETE nas tabelas de versão — tested by: tests/db/test_papeis.py::test_app_sem_update_delete
- [ ] SPEC-001-AC-10: nenhuma coluna monetária usa tipo de ponto flutuante (INV-14) — tested by: tests/db/test_esquema.py::test_dinheiro_numeric
- [ ] SPEC-001-AC-11: existe campo de versão e a chave de idempotência é única por usuário — tested by: tests/db/test_idempotencia_esquema.py::test_chave_unica_por_usuario

## Notes

Comportamento de idempotência e conflito é testado na SPEC-004; aqui nasce só o esquema.
