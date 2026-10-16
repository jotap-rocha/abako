# 023 — Reserva, compromissos vs. disponível, recorrentes e vale

**Status:** Aceita
**Data:** 2026-10-16
**Autores:** time
**Reversibilidade:** difícil

---

## Contexto

Transformar as regras de produto (R1..R7) em definições numéricas testáveis.

## Decisão

1. **Níveis da reserva** (parametrizáveis): saudável ≥ 100% da meta; atenção de 50% a < 100%; crítica < 50%.
2. **R1** mostra nível, falta e, opcionalmente, o aporte mensal até uma data-alvo.
3. **Recorrentes:** cadastro (nome, tipo fixo/receita, valor esperado, dia do mês, conta, vigência); uma ocorrência por mês; vincular uma transação marca como paga.
4. **R2 (horizonte parametrizável, inicial 10 dias; parâmetro com vigência):**
   - `disponível` = saldos das contas correntes (exclui reserva e benefício) + receitas recorrentes com data ≥ hoje no horizonte, não vinculadas, com destino em conta corrente.
   - `compromissos` = fixos recorrentes não vinculados com data ≥ hoje no horizonte + **faturas PRÓPRIAS** com vencimento no horizonte (total − terceiros).
   - `sobra = disponível − compromissos`; alerta se < 0.
   - Fatura aberta aparece como "parcial"; ocorrências vencidas e não vinculadas são listadas à parte; o crédito do vale nunca entra no disponível.
   - A fatura é exibida como "total = própria + terceiros" (por pessoa, rótulo "a receber"), mas a **sobra usa só a própria**.
5. **R4** lista contas/faturas onde derivado ≠ snapshot.
6. **Vale (conta de benefício única):**
   - Despesas de benefício **nunca** entram no gasto real **nem aparecem na tela principal** (só na página de métricas do vale).
   - Receita se divide em caixa (tela principal), vale e total (só na página de métricas).
   - Base de trabalho R$ 200 (parâmetro com vigência); `pessoal = crédito do mês − base de trabalho`; crédito do mês = receitas lançadas na conta de benefício no mês civil.
   - Alocação efetiva = base + ajuste de sobra; consumo/resta por bolso; alerta se resta < 0; toda despesa do vale exige bolso (padrão sugerido: pessoal).
7. **Sobra do vale** = Σ max(resta, 0) por bolso, **sem compensar estouros**. Decisão manual (trabalho / pessoal / nenhum; destino padrão = parâmetro, inicial "nenhum"). A decisão é um **evento com histórico**, soma na alocação do destino no mês seguinte, **não move saldo** e fica pendente até ser decidida. O saldo total do vale é o saldo derivado normal (acumula), conferido por snapshot.
8. **Apresentação:** a tela principal mostra receita de caixa, gasto real, sobra R2 (fatura própria e total), reserva e alertas. A página do vale mostra crédito, consumo, resta, sobra, decisão, saldo total e receita total.

**R5** é o alerta do vale por bolso: dispara quando o `resta` de um bolso (trabalho ou pessoal) fica negativo, sem compensação pela sobra do outro (INV-25, fixture F-VALE-03). Não tem relação com fatura nem com saldo da conta corrente.

Alertas da v1: R1, R2, R4, R5. Ficam para depois: R3 (limite), R6 (receber), R7 (categoria fora).

## Alternativas consideradas

### Opção A — Vale como despesa comum ❌ Rejeitada
Distorce o gasto real.

### Opção B — Terceiros na sobra do R2 ❌ Rejeitada
Superestima o compromisso.

### Opção C — Compensar estouros entre bolsos ❌ Rejeitada
Esconde o excesso.

### Opção D — Regras desta decisão ✅ Escolhida

## Consequências

### Positivas
- Regras com exemplos numéricos (fixtures F-RES, F-R2, F-VALE).

## Premissas

O vale é uma conta única; a base de trabalho muda raramente; a semântica de limite e fechamento ainda precisa de confirmação.

## Fora de escopo

Categorização do essencial pago pelo vale; alertas R3/R6/R7; projeção além de 10 dias.

## Como verificar

INV-17..INV-26; fixtures numéricas (reserva com meta 12.000: 3.000 e 5.999,99 críticas, 6.000 atenção, 12.000 saudável; R2 5.000+3.000−2.500−4.200 = 1.300, e com 6.000 = −500; vale crédito 1.000 → trabalho 200, pessoal 800).

## Impacto em SI/LGPD

Dado financeiro pessoal; sem impacto adicional.

## Revisão

Revisar após confirmar a semântica de limite/fechamento dos cartões.
