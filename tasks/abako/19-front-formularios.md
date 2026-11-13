# SPEC-012 (5/5): formulários restantes

**Status:** done  
**Blocked by:** tasks/abako/18-front-leitura.md

## What to build

Formulários de estorno, pessoas e repasse (compra 100% própria ou 100% de terceiro, sem divisão),
recorrentes (com ocorrências do mês e vínculo), fechamento e vencimento do cartão com vigência e
parâmetros em `/parametros` (meta da reserva e horizonte do R2, com histórico de vigências). Também
prova a PWA instalável e sem cache de resposta autenticada. O front só envia e exibe o que a API
devolve (ADR 015); decisões de tela no ADR 051. Sem mudança no backend.

## Acceptance criteria

- [x] SPEC-012-AC-15: formulário de estorno distingue integral de com parcelas pagas — tested by: frontend/src/estorno/Estorno.test.tsx::tipos_de_estorno
- [x] SPEC-012-AC-16: repasse e despesa de terceiro enviam a pessoa e respeitam 100%/100% — tested by: frontend/src/terceiros/Terceiros.test.tsx::cem_por_cento
- [x] SPEC-012-AC-17: PWA instalável e sem cache de resposta autenticada — tested by: frontend/src/pwa/Pwa.test.ts::sem_cache_autenticado
- [x] SPEC-012-AC-18: pessoas (cadastro, renomear, excluir, a receber como a API devolveu) — tested by: frontend/src/terceiros/Terceiros.test.tsx::mostra_a_receber_como_a_api_devolveu
- [x] SPEC-012-AC-19: recorrentes (cadastro, ocorrências, vencidas, vínculo) — tested by: frontend/src/recorrentes/Recorrentes.test.tsx::vincula_e_desvincula_e_mostra_a_recusa
- [x] SPEC-012-AC-20: fechamento e vencimento do cartão com vigência — tested by: frontend/src/cartao/ConfigCartao.test.tsx::grava_fechamento_com_vigencia_e_atualiza_a_fatura
- [x] SPEC-012-AC-21: parâmetros da reserva e horizonte do R2 com histórico — tested by: frontend/src/parametros/Parametros.test.tsx::grava_a_meta_da_reserva_com_vigencia
- [x] SPEC-012-AC-22: escrita distingue os dois 409 pelo código e mostra o 422 literal — tested by: frontend/src/api/escrita.test.ts::distingue_os_dois_409_pelo_codigo_e_nao_pelo_texto
- [x] SPEC-012-AC-23: jornada pessoa, compra de terceiro, repasse e a receber — tested by: tests/e2e/test_formularios.py::test_pessoa_compra_de_terceiro_repasse_e_a_receber
- [x] SPEC-012-AC-24: jornada estornar uma compra — tested by: tests/e2e/test_formularios.py::test_estornar_compra

## Notes

Os critérios completos (com todos os testes de cada um) estão em `tests/contracts/criterios.yaml`.
Os ids AC-12 a AC-14 já pertencem à task 18; por isso os critérios desta task começam em AC-15.
Design provisório (mesma base visual das telas anteriores); o usuário ajusta depois.
