# 046 — Gasto real e receita de caixa: convenções da SPEC-008

**Status:** Aceita
**Data:** 2026-11-12
**Autores:** time
**Reversibilidade:** fácil (só leituras derivadas; nada é gravado)

---

## Contexto

Os ADRs 007, 009, 011, 020, 023 e 044 definiram o que é e o que não é gasto real, mas não a
conta exata: de qual data vem cada tipo, o que fazer com débito em conta de reserva, onde fica a
receita de caixa. Esta SPEC calcula o gasto real do mês e a receita do mês. As decisões abaixo
foram tomadas pelo usuário em 2026-11-12.

## Decisão

1. **Gasto real do mês = despesas próprias do usuário.** Exclui transferência, investimento
   (aporte), repasse, rendimento (e o imposto retido dele), pagamento de fatura (que é uma
   transferência), compra de terceiro e **qualquer** conta de benefício (INV-04, 05, 11, 20).
   Soma só duas origens: débito/pix e parcela de compra a crédito.
2. **Débito/pix conta pela data do lançamento**, no mês civil (`data_transacao`, data civil de
   `America/Sao_Paulo`, ADR 012). **Crédito conta por parcela, na competência da fatura**
   (ADR 011 e 043), lendo `parcela_ativa`. O valor da compra inteira nunca é contado de uma vez.
3. **Estorno (ADR 044 item 5):** `parcela_ativa` já não traz as parcelas de compra estornada, então
   o estorno tira a compra do gasto real nas competências **originais** das parcelas, inclusive de
   meses já fechados. O crédito P do estorno **não** é receita nem redutor adicional de gasto
   (contaria duas vezes). Estorno parcial ou integral produz o mesmo efeito no gasto: a compra sai.
4. **Terceiros fora do gasto (INV-11):** parcela com `pessoa_id` não nulo não entra. A mesma
   parcela segue na fatura e no limite (ADR 045).
5. **Débito em conta de reserva ou de investimento conta como gasto**: é consumo de dinheiro do
   usuário, só mudou de onde saiu. O que não conta é a **transferência** e o **aporte**
   (investimento), que apenas movem dinheiro entre contas do usuário.
6. **Conta de benefício** é decidida pelo tipo **vigente** da conta no momento da consulta.
   O banco recusa trocar o tipo de uma conta que já tem lançamentos (de ou para benefício), então na
   prática meses passados não são reescritos; se essa trava um dia cair, o gasto e a receita dos
   meses passados passam a ser reescritos retroativamente (efeito aceito). Débito
   dela nunca entra no gasto real; a compra a crédito não existe nela (só em conta de cartão).
7. **Receita de caixa do mês** = lançamentos do tipo `receita`, pela data do lançamento, em conta
   que **não** é de benefício. Exclui repasse, rendimento e benefício (INV-20, INV-12). **Receita
   de benefício** = o `receita` em conta de benefício. **Receita total** = caixa + benefício
   (INV-24); a visão principal usa só a de caixa e o crédito do vale nunca entra nela.
8. **Mês é parâmetro explícito**, texto `AAAA-MM` (mesmo formato da competência). Padrão "mês
   corrente" é da camada de API. Mês fora do formato é recusado com `AB422` e mensagem literal.
9. **Leituras como funções `INVOKER`** que recebem o `user_id` da sessão (INV-13), sem escrita:
   `mes_inicio`, `gasto_real_itens` (origem, conta, valor), `gasto_real` (total),
   `gasto_real_por_conta`, `receita_caixa`, `receita_beneficio`, `receita_total`. O modelo atual não
   tem categoria; não há "gasto por categoria" até a SPEC que a criar.
10. **Papéis:** `abako_app` executa as funções; `PUBLIC` não. `abako_pipeline` **não** ganha EXECUTE:
    o analítico (SPEC-014) lê as views `transacao_vigente`/`parcela_ativa` (que não têm nome de
    pessoa) e agrega por conta própria, ou ganha uma função própria nessa SPEC. As funções devolvem
    só ids e valores.
11. **Mensagens de erro** literais (sem `||`, nome, valor ou id), com teste estático sobre o SQL
    da 0009.

## Consequências

- Migração 0009: só funções (nenhuma tabela nem coluna). Downgrade as remove; é seguro com dados.
- Pendente de API (fin-backend): rota de gasto real e receita do mês (mês padrão = corrente, em
  `America/Sao_Paulo`), com dinheiro em texto, `user_id` da sessão e nome de pessoa fora do log.
- A tela principal (SPEC-012/018) apenas exibe o que a API devolver.

## Alternativas consideradas

- Débito em reserva fora do gasto ❌: é consumo real; esconderia gasto que sai do colchão.
- Crédito do estorno como receita ou como gasto negativo ❌: duplica o efeito de tirar a compra.
- Contar a compra a crédito inteira na data da compra ❌: contradiz o ADR 011 e distorce o mês.
- Gravar o gasto do mês ❌: dado derivado duplicado sujeito a divergir; o estorno em mês fechado
  exigiria reescrever o passado.

## Fora de escopo

Gasto por categoria; metas e orçamento (apertado/folgado) por cima do gasto; reserva (SPEC-009);
vale (SPEC-013); agregação no analítico (SPEC-014).

## Como verificar

INV-04, 05, 11, 20 e parte do 24; fixtures F-GASTO-01 a F-GASTO-03; critérios SPEC-008-AC-1 a AC-10.

## Impacto em SI/LGPD

Dado financeiro pessoal (ADR 014). As funções são leituras puras, filtradas pelo `user_id` da sessão
(INV-13): chamadas com o `user_id` de outro usuário devolvem zero/vazio. Não devolvem nome de pessoa
nem descrição livre; mensagens de erro são literais; nada vai a log, URL ou serviço externo. O
pipeline não recebe acesso às funções nesta SPEC. Finalidade e minimização inalteradas: só o
cálculo do próprio usuário sobre os próprios lançamentos.
