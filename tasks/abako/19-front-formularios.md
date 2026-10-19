# SPEC-012 (5/5): formulários restantes

**Status:** not started  
**Blocked by:** tasks/abako/18-front-leitura.md

## What to build

Formulários de estorno, terceiros e repasse, recorrentes, fechamento do cartão com vigência e parâmetros (meta da reserva, horizonte do R2).

## Acceptance criteria

- [ ] SPEC-012-AC-13: formulário de estorno distingue integral de com parcelas pagas — tested by: frontend/src/estorno/Estorno.test.tsx::tipos_de_estorno
- [ ] SPEC-012-AC-14: repasse e despesa de terceiro enviam a pessoa e respeitam 100%/100% — tested by: frontend/src/terceiros/Terceiros.test.tsx::cem_por_cento
- [ ] SPEC-012-AC-15: PWA instalável e sem cache de resposta autenticada — tested by: frontend/src/pwa/Pwa.test.ts::sem_cache_autenticado

## Notes

Rascunho: os critérios são formalizados em `tests/contracts/criterios.yaml` quando a SPEC for escrita.
