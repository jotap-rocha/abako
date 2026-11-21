# 055 — Cadastro do cartão e da linha de crédito: convenções da task 22 (SPEC-012)

**Status:** Aceita
**Data:** 2026-11-20
**Autores:** dono do projeto e especialista de negócio (decisões), time (implementação)
**Reversibilidade:** alta (só tela e uma camada de API do front; sem tabela, migração nem mudança de contrato)

---

## Contexto

A API já criava linha de crédito, cartão (conta tipo `divida` com `linha_credito_id`) e fechamento,
mas o front não tinha como cadastrá-los: sem cartão, o usuário não lança compra no crédito. O ADR
015 proíbe regra de cálculo no front; os ADR 043 e 044 definem linha, limite compartilhado,
fechamento e fatura; os ADR 050 e 051 definem as convenções das telas e da escrita tipada.

## Decisão

1. **Seção própria "Novo cartão" dentro de Cartões**, não um tipo no formulário de Contas. O tipo
   `divida` continua fora do formulário genérico (evita criar cartão sem linha por engano).
2. **Linha primeiro, cartão depois.** O formulário cria a linha (nome e limite em texto) e o cartão
   ligado a ela, ou escolhe uma linha existente (vários cartões na mesma linha compartilham o
   limite, ADR 043 item 6). Todo cartão tem linha. Não se oferece trocar a linha de um cartão
   existente nem excluir linha ou cartão.
3. **Fechamento junto e opcional**: dia (1 a 31) e "vale a partir de", que vem preenchido com o
   **1º dia do mês atual** (o dono vai lançar só compras novas; é só preenchimento editável, vindo de
   `datas.ts`) com a ajuda "compras anteriores a esta data são recusadas". Sem fechamento, a tela
   de Cartões mostra o aviso persistente "sem fechamento, a compra no crédito será recusada". O
   critério é o que a API já devolve na fatura (`situacao` e `fechamento` nulos); o front não calcula.
4. **Falha parcial sem endpoint novo.** Ordem: linha, cartão, fechamento. Linha criada e cartão
   falhou: a tela mostra o erro, trava os campos da linha e a nova tentativa reutiliza a linha já
   criada. Cartão criado e fechamento falhou: "cartão criado, falta o fechamento", com botão que
   leva ao `ConfigCartao` daquele cartão. Duplo clique: botão desabilitado e guarda com `useRef`
   (como no estorno, ADR 051 item 3). 409 AB410 = nome repetido; 422 = mensagem literal do banco.
5. **Editar a linha** (nome e limite) com `versao` (409 AB409 = "mudou desde a leitura", recarrega).
   **Limitação registrada: o limite não tem vigência por data**; o limite novo vale para tudo,
   inclusive o passado, e para todos os cartões da linha. O texto fixo está na tela.
6. **Dívida inicial: começar do zero.** Sem saldo inicial; a tela avisa que parcelas antigas ainda
   em aberto precisam ser lançadas uma a uma.
7. **Limite como texto**, digitado no jeito brasileiro e traduzido por `lerValorDigitado` (só troca
   caracteres) para o formato do servidor `^[0-9]{1,12}(\.[0-9]{1,2})?$`; negativo é barrado na
   tela e o banco continua sendo a autoridade. Acessibilidade e privacidade como no ADR 051
   itens 9 e 10; nome de linha e de cartão é renderizado como texto.
9. **Ajustes da revisão.** "Usar outra linha" descarta a referência à linha criada quando o cartão
   falhou (a linha criada fica sem cartão; não há exclusão). Modo "linha existente" com lista vazia
   mostra "Nenhuma linha cadastrada ainda. Crie uma nova linha." e bloqueia o envio, sem marcar
   campo inexistente. "Cadastrar o fechamento" move o **foco** para o bloco de fechamento e
   vencimento, e o aviso "falta o fechamento" some quando o fechamento é gravado ali. Na edição da
   linha, nome repetido (409 AB410) aparece no campo e o aviso de versão velha some ao digitar.
   O e2e lança a compra no 1º dia do mês atual para não depender do dia em que roda (compra no dia
   do fechamento cai na fatura seguinte, ADR 043).
8. **Carga preguiçosa**: a lista de linhas só é buscada quando o usuário escolhe "linha existente"
   ou pede para editar a linha, para a tela de Cartões não ganhar chamadas nem falhas novas.

## Fora de escopo

Excluir linha ou cartão (não existe), trocar a linha de um cartão com lançamentos, vigência por
data para o limite, mudar o tipo de uma conta, endpoint que crie cartão e fechamento numa chamada,
snapshot de cartão com sinal automático, pagamento de fatura, alertas.

## Dívidas registradas

- Sem transação única: o usuário pode ficar com linha criada sem cartão (reaproveitável, mas não
  excluível) ou cartão sem fechamento (avisado na tela).
- O aviso de "sem fechamento" é por fatura exibida; a lista de cartões não marca qual está sem.
- "Vale a partir de" no **futuro**: a fatura passa a mostrar um fechamento (sem o aviso de "sem
  fechamento"), mas a compra de hoje ainda é recusada pelo servidor. A ajuda "compras anteriores a
  esta data são recusadas" só aparece no formulário; a tela de Cartões não repete isso.

## Consequências

- Nenhuma mudança no backend, no contrato OpenAPI ou no cliente gerado.
- Critérios SPEC-012-AC-25 a AC-30 em `tests/contracts/criterios.yaml`.

## Como verificar

`frontend/src/cartao/NovoCartao.test.tsx`, `tests/e2e/test_cartao.py`.

## Impacto em SI/LGPD

Nenhum dado novo é coletado ou guardado. Nome de linha, nome de cartão e limite são dado financeiro
pessoal enviado só à API do próprio usuário, na sessão autenticada; o `user_id` vem da sessão
(INV-13), nunca do corpo. Nada vai a URL, storage ou console (a varredura do ADR 051 item 10 cobre o
código novo). Mensagens de erro do banco são literais e sem valores.
