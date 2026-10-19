# SPEC-014: pipeline e analítico

**Status:** not started  
**Blocked by:** tasks/abako/20-vale-r5.md

## What to build

Pipeline Postgres→DuckDB: papel somente leitura, recomputo completo, troca atômica do arquivo, trava contra execução simultânea, painel analítico só com agregados.

## Acceptance criteria

- [ ] SPEC-014-AC-1: o pipeline escreve só no analítico (INV-15) — tested by: tests/pipeline/test_fluxo.py::test_nao_escreve_no_transacional
- [ ] SPEC-014-AC-2: reexecutar produz agregados idênticos e a soma bate com o transacional — tested by: tests/pipeline/test_idempotencia.py::test_reexecucao_identica
- [ ] SPEC-014-AC-3: duas execuções simultâneas são impedidas e a segunda não toca o arquivo (INV-35) — tested by: tests/pipeline/test_trava.py::test_execucao_simultanea
- [ ] SPEC-014-AC-4: falha mantém o arquivo anterior — tested by: tests/pipeline/test_troca_atomica.py::test_falha_mantem_anterior

## Notes

Rascunho: os critérios são formalizados em `tests/contracts/criterios.yaml` quando a SPEC for escrita.
