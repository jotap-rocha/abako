# 021 — Estrutura do repositório e estratégia de testes

**Status:** Aceita
**Data:** 2026-10-16
**Autores:** time
**Reversibilidade:** difícil

---

## Contexto

Agentes e revisor precisam de convenções claras e testes objetivos.

## Decisão

- Módulos pequenos; `tests/contracts/` (invariantes e critérios) e `fixtures/`.
- Ferramentas: **pytest** (SQL + backend), **Hypothesis** (inclui `RuleBasedStateMachine`), **Vitest + React Testing Library**, **Playwright** (poucas jornadas) e testes dos hooks/gitleaks.
- Banco `tst` vazio e descartável; a suíte aborta se a conexão não for `tst`.
- **IDs de critério** (ex.: `SPEC-003-AC-2`) e um script que lista critérios e invariantes **sem teste**.
- Comando único **`check`**; o revisor só recebe entrega com `check` verde.
- Invariantes **INV-01..INV-26** em `tests/contracts/invariantes.yaml`.

## Alternativas consideradas

### Opção A — Só testes de integração ❌ Rejeitada
Não isolam a regra.

### Opção B — Mocks do banco ❌ Rejeitada
A regra está no SQL.

### Opção C — Pirâmide com contratos rastreáveis ✅ Escolhida

## Consequências

### Positivas
- Cobertura rastreável critério → teste.

## Premissas

Testes rodam local e em CI com Postgres efêmero.

## Fora de escopo

Testes de carga; mutation testing.

## Como verificar

O script de rastreabilidade retorna vazio; `check` verde.

## Impacto em SI/LGPD

Fixtures são inventadas e anônimas; nunca usar dado real em teste.

## Revisão

Revisar quando a SPEC-001 definir o comando `check`.
