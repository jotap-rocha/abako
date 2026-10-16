# 017 — Revisor adversarial externo

**Status:** Aceita
**Data:** 2026-10-16
**Autores:** time
**Reversibilidade:** fácil

---

## Contexto

O usuário dispõe de um modelo externo (Gemini, plano com contexto de ~128K) para uma revisão independente do código.

## Decisão

- **Gemini** como revisor; fallback para um modelo mais leve com a instrução "recalcule cada exemplo numérico passo a passo".
- O **pacote de revisão nunca contém** dado real, `.env`, pasta de dados, backups ou dumps.
- Decisões (ADRs) **não** vão no pacote: só rubrica + SPEC + código + testes.
- Histórico de atividade do modelo desligado.
- **Uma passada por entrega + um reteste.** Achados voltam para classificação (procede / não procede / parcialmente).
- A rubrica é `docs/revisao/rubrica-adversarial.md`.

## Alternativas consideradas

### Opção A — Outro revisor externo ❌ Rejeitada
O usuário já tem acesso ao Gemini.

### Opção B — Gemini com rubrica autossuficiente ✅ Escolhida

## Consequências

### Positivas
- Revisão barata.

### Negativas / Tradeoffs
- Cobertura limitada pelo contexto.

## Premissas

O modelo Pro pode deixar de estar disponível; por isso a rubrica é autossuficiente.

## Fora de escopo

Múltiplos revisores; revisão contínua.

## Como verificar

O pacote passa por varredura de termos pessoais e arquivos proibidos antes do envio; só entregas com `check` verde são enviadas.

## Impacto em SI/LGPD

Envio de código a serviço externo: nunca incluir dado real nem segredo.

## Revisão

Revisar se o modelo ficar indisponível.
