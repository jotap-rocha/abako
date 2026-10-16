# 016 — Frota de agentes, skills e KBs do projeto

**Status:** Aceita
**Data:** 2026-10-16
**Autores:** time
**Reversibilidade:** fácil

---

## Contexto

O harness traz muitos agentes, skills e KBs genéricos. O projeto deve usar só o que exige.

## Decisão

- Usar só o necessário; agentes novos com prefixo `fin-`.
- **Novo agente `fin-frontend`** (`.claude/agents/fin/fin-frontend.md`).
- **KBs novas:** `react-pwa`, `postgres-financeiro`, `seguranca-local`.
- **Skills:** o usuário as busca em catálogos públicos por assunto (lista em `.claude/projetos/sisfin/03-harness.md`).
- `CLAUDE.md` mapeia só as KBs relevantes, com caminhos exatos.

## Alternativas consideradas

### Opção A — Criar skills aqui ❌ Rejeitada
O usuário prefere buscar skills prontas.

### Opção B — Frota enxuta + 1 agente + 3 KBs ✅ Escolhida

## Consequências

### Positivas
- Descrição de agentes dentro do orçamento de contexto.

## Fora de escopo

Agentes de real-time e ML.

## Como verificar

A lista de agentes, skills e KBs do projeto bate com `03-harness.md`.

## Impacto em SI/LGPD

Skills de terceiros devem ser revisadas antes de instaladas (ver KB `seguranca-local`).

## Revisão

Revisar a cada nova camada do sistema.
