# SPEC-014: pipeline e analítico

**Status:** done  
**Blocked by:** tasks/abako/20-vale-r5.md
**ADR:** docs/adr/054-pipeline-analitico-duckdb.md

## What to build

Pipeline Postgres→DuckDB (`python -m pipeline`): papel somente leitura, transação REPEATABLE READ,
recomputo completo, arquivo novo + troca atômica, trava contra execução simultânea, só agregados
(`saldo_diario`, `gasto_mensal`, `fatura_resumo`, `limite_linha`, `cobertura_reserva`, `a_receber`
só o total) e leitura somente leitura (`python -m pipeline.ler`). Migração 0014: `EXECUTE` mínimo de
15 leituras ao `abako_pipeline`. Sem rota de API nem tela.

## Acceptance criteria

Definição completa em `tests/contracts/criterios.yaml` (SPEC-014-AC-1 a AC-11).

- [x] SPEC-014-AC-1: o pipeline escreve só no analítico e o analítico só tem agregados (INV-15) — tested by: tests/pipeline/test_fluxo.py::test_nao_escreve_no_transacional
- [x] SPEC-014-AC-2: reexecutar produz agregados idênticos e a soma bate com o transacional — tested by: tests/pipeline/test_idempotencia.py::test_reexecucao_identica
- [x] SPEC-014-AC-3: duas execuções simultâneas são impedidas e a segunda não toca o arquivo (INV-35) — tested by: tests/pipeline/test_trava.py::test_execucao_simultanea
- [x] SPEC-014-AC-4: falha mantém o arquivo anterior e não deixa .tmp — tested by: tests/pipeline/test_troca_atomica.py::test_falha_mantem_anterior
- [x] SPEC-014-AC-5: valores das fixtures F-PIPE-01 (à mão) — tested by: tests/pipeline/test_agregados.py::test_f_pipe_01_valores_da_fixture
- [x] SPEC-014-AC-6: isolamento por user_id (INV-13) — tested by: tests/pipeline/test_agregados.py::test_f_pipe_02_isolamento_por_user_id
- [x] SPEC-014-AC-7: log sem dado financeiro, nome ou descrição — tested by: tests/pipeline/test_log.py
- [x] SPEC-014-AC-8: papel sem escrita e EXECUTE mínimo — tested by: tests/pipeline/test_papel.py
- [x] SPEC-014-AC-9: leitura somente leitura — tested by: tests/pipeline/test_ler.py
- [x] SPEC-014-AC-10: guardas de alvo e de pasta — tested by: tests/pipeline/test_config.py
- [x] SPEC-014-AC-11: sem nome nem descrição no arquivo — tested by: tests/pipeline/test_fluxo.py

## Notes

A 0014 foi aplicada só em `tst`. Aplicar em `prd` depende de aprovação humana (ADR 019).
