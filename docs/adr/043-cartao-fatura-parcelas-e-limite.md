# 043 — Cartão, fatura, parcelas e limite: convenções da SPEC-005

**Status:** Aceita
**Data:** 2026-11-10
**Autores:** time
**Reversibilidade:** difícil

---

## Contexto

A SPEC-005 traz o cartão como conta de dívida, a fatura por competência, o parcelamento e a linha
de crédito compartilhada (ADR 006, 011, 013, 027). Os ADRs deixaram em aberto como o saldo da
dívida se relaciona com o limite, em qual fatura cai a compra no dia do fechamento, o que é
"pagar a fatura" e quanto disso entra nesta SPEC. Decisões do usuário em 2026-11-10.

## Decisão

1. **Compra no dia do fechamento entra na fatura seguinte.** A fatura de competência M reúne as
   compras com data anterior ao fechamento de M (e posterior ou igual ao fechamento de M−1).
   Fecha ADR 027; fixture F-FECH-02.
2. **Competência = mês do fechamento** (exemplo: "2026-04"). O dia de vencimento não entra nesta
   SPEC; fica para a SPEC-010 (R2), que é quem o usa.
3. **Saldo da dívida é negativo (devo).** A compra no cartão (`credito`) é gravada com valor
   negativo na conta de dívida; a API continua recebendo o valor positivo e o tipo dá o sinal
   (ADR 042). **Cada parcela leva a data da compra**, e a **competência** da fatura fica numa
   coluna própria. Assim o saldo derivado da dívida (ADR 041, sem exceção por tipo) é o valor total
   ainda não pago e **limite usado = −(soma dos saldos das contas de dívida da linha)**, com
   parcelas futuras (INV-06). Compra à vista é a parcela 1 de 1.
4. **Pagar a fatura é um pagamento qualquer:** transferência da conta corrente para a conta de
   dívida (duas pernas, soma zero, INV-01), que abate a dívida e devolve limite. Pode ser
   **parcial**, como nos bancos. Não é tipo novo, não é gasto real (a compra é o gasto, na
   competência; INV-05) e não precisa apontar para uma fatura. O que significa "parcela paga"
   para estorno e edição (ADR 013) é decidido na SPEC-006, já sabendo que o pagamento é parcial.
5. **Fechamento com vigência por cartão** (dia 1 a 31, `vigente_desde`), versionado como o resto.
   Vale o dia vigente **na data da compra**; mudar o fechamento **não recalcula** compras já
   feitas. Dia inexistente no mês usa o último dia válido (INV-31). A competência de cada parcela é
   gravada e pode ser corrigida à mão (ADR 013); nunca é recalculada sozinha.
6. **Linha de crédito:** entidade com limite versionado; todo cartão pertence a uma linha.
   Limite disponível = limite − usado e **pode ficar negativo**: nada bloqueia a compra (o alerta
   R3 está adiado, ADR 023).
7. **Parcelas:** n de 1 a 48; as n−1 primeiras valem o total dividido por n truncado em centavos
   e a última absorve o resto (INV-02, F-PARC-01/02/03). Sem juros.
8. **Fora desta SPEC:** terceiros (`pessoa`) e repasse, que ficam na SPEC-007 (por isso o teste de
   "própria + terceiros" da fatura e o limite com terceiros só fecham lá, F-FAT-01 e F-LIM-01);
   estorno (SPEC-006); snapshot e R4 de fatura (adiados; a conta de dívida já aceita "informar
   saldo", ADR 041, mas isso não distingue fatura aberta de fechada); vencimento (SPEC-010).

## Consequências

- Migração 0006: tipo de conta `divida`, `linha_credito`, fechamento com vigência, colunas
  `parcela` e `competencia` em `transacao_versao`, ramo de `credito` nas restrições e em
  `lancamento_gravar`, e funções de fatura e de limite. Escrita só por funções (ADR 042).
- Pagar com valor maior que a dívida deixa o saldo do cartão positivo (crédito a favor); não é
  tratado como erro nesta SPEC.
- O limite usado só é igual ao total das compras não pagas enquanto não houver estorno; a SPEC-006
  ajusta isso.

- `conta_versao.linha_credito_id` e `cartao_fechamento.conta_id` não têm chave estrangeira (os ids
  se repetem entre versões); a integridade vem das funções de escrita, as únicas com permissão.
- As funções de leitura (fatura, limite) confiam no `user_id` que recebem, como as de saldo;
  só `abako_app` tem EXECUTE e o `user_id` vem sempre da sessão (INV-13). Se outro papel ganhar
  EXECUTE, o isolamento passa a depender dele.
- O INV-26 (fatura = própria + terceiros) passa para a SPEC-007, onde terceiros existem; aqui a
  fatura soma só compras próprias.

## Alternativas consideradas

- Dívida positiva ❌: exigiria exceção por tipo na soma do saldo (ADR 041).
- Parcela datada no mês da fatura ❌: o saldo e o limite só veriam a dívida aos poucos, e o
  ADR 042 recusa data futura.
- Pagamento de fatura como tipo próprio ou vinculado a uma fatura ❌: pagamento parcial e
  antecipado ficariam sem lugar; a transferência já tem a mecânica certa.

## Como verificar

INV-02, 06, 07, 31 e as fixtures F-FECH-01/02/03, F-PARC-03, F-FAT-02, F-LIM-02 e F-PAG-01;
critérios SPEC-005-AC-1 a AC-10.

## Impacto em SI/LGPD

Nenhum dado novo além de valores e datas do próprio usuário. Toda tabela nova tem `user_id` e o
filtro vem da sessão (INV-13); a aplicação não ganha UPDATE/DELETE nas tabelas de versão.
