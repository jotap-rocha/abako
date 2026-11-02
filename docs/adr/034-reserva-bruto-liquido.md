# 034 — Reserva em bruto e líquido, com imposto retido

**Status:** Aceita
**Data:** 2026-10-19
**Autores:** time
**Reversibilidade:** moderada

---

## Contexto

O ADR 007 deixou imposto e rendimento fora de escopo. O usuário quer ver separado o que paga em imposto sobre o rendimento da reserva. O banco já desconta o imposto e mostra o valor.

## Decisão

- O **rendimento** passa a registrar **valor bruto** e **imposto retido**; o valor creditado na conta é bruto − imposto (líquido).
- O **saldo da reserva** é o da conta (líquido) e continua conferido por snapshot.
- A tela da reserva mostra **líquido**, **imposto acumulado** e **bruto** (= líquido + imposto acumulado).
- A **cobertura em meses** usa o líquido.
- O imposto não é gasto real, assim como o rendimento (INV-04).
- Complementa o ADR 007 (que fica como está).

## Alternativas consideradas

### Opção A — Só líquido ❌ Rejeitada
Não mostra quanto se paga em imposto.

### Opção B — Imposto como lançamento separado ❌ Rejeitada
O banco desconta na própria conta; um lançamento à parte duplicaria o valor.

### Opção C — Rendimento com bruto e imposto ✅ Escolhida

## Consequências

### Positivas
- Imposto visível sem alterar o saldo conferido pelo snapshot.

### Negativas / Tradeoffs
- O lançamento de rendimento exige dois valores.

## Como verificar

INV-36, INV-37; fixture F-RES-03 a criar na SPEC-009 (valores calculados à mão).

## Impacto em SI/LGPD

Dado financeiro pessoal; sem impacto adicional.

## Revisão

Revisar se IOF ou outros tributos precisarem de detalhamento.
