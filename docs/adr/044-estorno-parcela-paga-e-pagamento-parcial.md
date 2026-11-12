# 044 — Estorno e "parcela paga" com pagamento parcial: convenções da SPEC-006

**Status:** Aceita
**Data:** 2026-11-10 (revisado em 2026-11-11 com as decisões dos itens 8, 9 e 10)
**Autores:** time
**Reversibilidade:** difícil

---

## Contexto

O ADR 013 separa estorno integral (nenhuma parcela paga) de estorno com parcelas pagas (crédito na
próxima fatura aberta, líquido zero). O ADR 043 (item 4) definiu o pagamento da fatura como uma
transferência solta da conta corrente para a conta de dívida, que pode ser parcial e não aponta
para fatura nem parcela, e deixou para esta SPEC o que é "parcela paga". Decisões do usuário em
2026-11-10 (D1 a D9 do levantamento com o `abako-especialista`).

## Decisão

1. **"Parcela paga" é derivada, não registrada (D1, D3).** O pagamento continua solto. Por cartão
   (conta de dívida), o valor pago disponível para alocar é

   `pool = Σ pagamentos recebidos pelo cartão − Σ créditos de estorno já emitidos nele`

   e é alocado às parcelas vigentes do cartão em ordem crescente de **competência**, depois **data
   da compra**, depois **número da parcela**. Cada parcela recebe `min(valor da parcela, pool
   restante)`. O alocado a uma parcela é o "pago" dela. Não há estado de fatura aberta/fechada.
   Subtrair os créditos de estorno do pool evita contar duas vezes o mesmo dinheiro (o crédito
   já devolveu o que foi pago).
2. **Parcela paga em parte é dividida (D2, parte paga).** O valor pago de uma parcela vira
   crédito, mesmo que a parcela não esteja quitada. **P** = soma do alocado às parcelas da
   compra; **N = T − P** (T = total da compra).
3. **Estorno (D6):** transação nova de tipo `estorno`, ligada à compra original, que é preservada
   (SCD2; nada de apagá-la). Um estorno por compra, sempre da compra inteira (estorno parcial por
   item segue fora de escopo, ADR 013). Variação do saldo da dívida: **+T**.
   - **limite devolvido = N**; **crédito = P**, na próxima fatura aberta; **movimento em conta
     corrente = 0**; **líquido da compra = −T + N + P = 0** (INV-08).
   - Nenhum dinheiro vai à conta corrente (ADR 013).
4. **Próxima fatura aberta (D5):** é a competência que o estorno recebe se for lançado como uma
   compra na data do estorno, pela regra do ADR 043 item 1 (estorno no dia do fechamento cai na
   fatura seguinte) e pelo fechamento vigente (item 5). Sem estado novo de fatura.
5. **Gasto real (D7, refinável depois):** o estorno tira a compra do gasto real nas competências
   **originais** das suas parcelas, inclusive de meses já fechados (confirmado pelo usuário em
   2026-11-11: melhor corrigir o gasto passado do que ficar com valores errados). O crédito P é abatimento financeiro da fatura e **não** é
   receita nem redutor adicional de gasto, para não contar duas vezes. Interage com a SPEC-008.
6. **Alocação entre compras (D4):** a ordem do item 1 vale entre compras do mesmo cartão. Logo,
   estornar uma compra nova pode ser integral (P = 0) mesmo com pagamentos recentes, se eles
   foram alocados às compras anteriores.
7. **Saldo positivo (D8):** pagamento maior que a dívida e crédito de estorno deixam o saldo do
   cartão positivo; o limite disponível pode passar do limite contratado. Aceito, como no
   ADR 043. Excedente de pagamento não alocado fica no pool.
8. **Edição e exclusão de compra com parte paga são bloqueadas (D9, entra nesta SPEC).** Se o pago
   alocado à compra (P, item 2) for maior que zero, editar ou excluir a compra é recusado, com
   mensagem orientando a estornar e relançar. Compra sem nada pago continua editável e
   excluível (SPEC-005-AC-10). Isso substitui, para esta SPEC, o "recalcular só as parcelas não
   pagas" do ADR 013, que não é implementado. (Exclusão incluída por decisão do usuário em
   2026-11-11.)
9. **Depois de um estorno, nada do cartão se edita nem se apaga.** Em um cartão com estorno são
   recusados editar ou excluir **qualquer lançamento já gravado nele**: compras, pagamentos
   recebidos, a compra estornada e o próprio estorno. A recusa traz mensagem clara. Assim a
   alocação do pago não muda e o líquido zero não se perde. Lançamentos **novos** no cartão
   (compras, pagamentos) continuam permitidos. Converter um lançamento existente em compra ou
   pagamento de um cartão com estorno também é recusado, pois mudaria a alocação do pago.
   Desfazer um estorno não existe nesta SPEC.
   (Decisão do usuário, 2026-11-10 e 2026-11-11.)
10. **Faturas antigas não mudam.** O estorno só tira as parcelas da compra das faturas de
    competência igual ou posterior à do crédito (item 4). Faturas de competência anterior mantêm
    o mesmo valor, e o crédito P aparece na competência do estorno. Isso vale para a fatura e
    não muda o item 5 (gasto real). Parcela não paga (atrasada) de fatura antiga continua
    aparecendo nela, mas seu valor faz parte de N e **devolve limite** ao cartão; o crédito
    continua sendo só P. (Decisão do usuário, 2026-11-11.)
11. **Juros e encargos (D2, parte não paga): adiado.** Este ADR trata a parte não paga pelo
    ADR 013 (devolve limite) e o ADR 043 item 7 (sem juros). Como os bancos tratam encargos e
    crédito no estorno após pagamento parcial varia de banco para banco; o usuário vai pesquisar e
    definir um denominador comum depois.

## Consequências

- Nova migração: tipo `estorno` com vínculo à compra, restrição de um estorno por compra, função
  de alocação (leitura) e função de escrita do estorno (ADR 042: escrita só por funções, sem
  UPDATE/DELETE para a aplicação).
- As faturas por competência e o gasto real passam a descontar as parcelas de compras estornadas;
  o saldo e o limite passam a refletir +T (ADR 043 consequência: o limite usado deixa de ser só
  o total das compras não pagas).
- O resultado do estorno depende do histórico de pagamentos. Por isso (item 9) o cartão com
  estorno fica imutável, e o pool nunca fica negativo.
- A alocação é recomputada a cada consulta; não é gravada. Exige índice/consulta por cartão.

## Alternativas consideradas

- Parcela paga só quando totalmente coberta ❌: deixa dinheiro pago sem crédito e quebra o
  líquido zero (INV-08).
- Pagamento vinculado a fatura ou parcela ❌: rejeitado no ADR 043.
- Cancelar a compra por exclusão lógica e criar o crédito ❌: some do gasto real sem rastro.
- Alocação proporcional entre compras ❌: menos determinística de testar que a ordem cronológica.

## Fora de escopo

Juros, multa e encargos por banco (item 11); chargeback; estorno parcial por item; desfazer
estorno; estado de fatura (aberta/fechada/paga) e snapshot de fatura.

## Como verificar

INV-08; fixtures F-EST-01 a F-EST-06 (a 06 é a edição bloqueada); critérios SPEC-006-AC-1 a AC-10.

## Impacto em SI/LGPD

Nenhum dado novo além de valores e datas do próprio usuário. A nova tabela/colunas levam `user_id`
e o filtro vem da sessão (INV-13).
