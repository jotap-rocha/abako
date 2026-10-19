# SPEC-004: lançamento por tipo e edição versionada

**Status:** not started  
**Blocked by:** tasks/abako/07-saldo-snapshot.md

## What to build

Lançamento manual dos sete tipos (débito/pix, crédito, receita, transferência, investimento, repasse, rendimento com bruto e imposto retido), edição que cria nova versão, exclusão lógica, idempotência de criação e conflito em atualização desatualizada.

## Acceptance criteria

- [ ] SPEC-004-AC-1: transferência tem duas pernas e soma zero (INV-01) — tested by: tests/db/test_transferencia.py::test_duas_pernas_soma_zero
- [ ] SPEC-004-AC-2: editar cria nova versão, preserva histórico e só a vigente conta (INV-09) — tested by: tests/db/test_versionamento.py::test_edicao_cria_versao
- [ ] SPEC-004-AC-3: repetir a criação com a mesma chave não duplica (INV-28) — tested by: tests/backend/test_idempotencia.py::test_mesma_chave_nao_duplica
- [ ] SPEC-004-AC-4: atualização com versão desatualizada retorna conflito 409 (INV-29) — tested by: tests/backend/test_conflito.py::test_versao_desatualizada
- [ ] SPEC-004-AC-5: exclusão é lógica e a transação deixa de contar — tested by: tests/db/test_exclusao.py::test_exclusao_logica
- [ ] SPEC-004-AC-6: rendimento registra bruto e imposto; o creditado na conta é bruto − imposto e não é gasto real (INV-36) — tested by: tests/db/test_rendimento.py::test_liquido_creditado

## Notes

Rascunho: os critérios são formalizados em `tests/contracts/criterios.yaml` quando a SPEC for escrita.
