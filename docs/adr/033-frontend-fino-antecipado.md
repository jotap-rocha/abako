# 033 — Frontend fino antecipado (SPEC-012 em incrementos)

**Status:** Aceita
**Data:** 2026-10-19
**Autores:** time
**Reversibilidade:** fácil

---

## Contexto

O ADR 028 deixou o frontend (SPEC-012) para depois das regras financeiras. O usuário precisa ver o app cedo e vai ditar, orientar e exemplificar os designs de tela; o design só se valida com tela real.

## Decisão

- A SPEC-012 continua sendo uma SPEC (mesmos IDs `SPEC-012-AC-N`), entregue em **5 tasks** (06, 08, 10, 18 e 19): (1) casca e login logo após a SPEC-002; (2) saldos e snapshot após a SPEC-003; (3) formulário de lançamento após a SPEC-004; (4) telas de leitura após os alertas (SPEC-011); (5) formulários restantes.
- A tela do vale nasce com a SPEC-013.
- Nenhuma regra financeira no front (ADR 015); o front só consome a API.
- Substitui apenas a posição da SPEC-012 na ordem do ADR 028; as demais posições e a numeração das SPECs ficam como estão.

## Alternativas consideradas

### Opção A — Frontend só no fim (ADR 028) ❌ Rejeitada
O usuário só veria o app depois de 11 SPECs; o design não seria validado cedo.

### Opção B — Uma tela por SPEC financeira ❌ Rejeitada
Mistura regra e interface; pior para revisar.

### Opção C — Incrementos de frontend intercalados ✅ Escolhida

## Consequências

### Positivas
- Feedback de design cedo; jornadas e2e desde o início.

### Negativas / Tradeoffs
- Retrabalho de tela quando uma regra mudar; contratos OpenAPI precisam ficar estáveis.

## Como verificar

`tasks/README.md`; `SPEC-012-AC-*` distribuídos pelas tasks 06, 08, 10, 18 e 19.

## Impacto em SI/LGPD

Nenhum além do ADR 031.

## Revisão

Revisar se o retrabalho de tela ficar alto.
