# SPEC-012 (6/6): cadastro do cartão de crédito e da linha de crédito

**Status:** done  
**Blocked by:** tasks/abako/19-front-formularios.md (tela de Cartões, fechamento e vencimento já existem)

## What to build

Hoje a API cria linha de crédito (`POST /api/linhas-credito`), cartão (`POST /api/contas` com tipo
`divida` e `linha_credito_id`) e fechamento, mas **o front não tem como criar o cartão nem a linha**:
o formulário de conta não oferece o tipo cartão e `criarConta` não envia `linha_credito_id`. Sem isso
o usuário não consegue lançar compras no crédito. Esta task é só front (nenhuma regra nova, nenhuma
migração): uma seção **"Novo cartão" dentro da tela de Cartões**.

Decisões do dono (2026-11-20) e do especialista (registrar no ADR 055):

- **Seção própria em Cartões**, e não mais um tipo no formulário de Contas. O tipo `divida` continua
  fora do formulário genérico (evita criar cartão sem linha por engano).
- **Linha primeiro, cartão depois.** O formulário cria a linha (nome e limite, em texto) e o cartão
  ligado a ela; ou escolhe uma linha existente (vários cartões na mesma linha = limite compartilhado,
  ADR 043 item 6). Todo cartão tem linha (o banco recusa sem ela).
- **Fechamento no mesmo formulário, opcional.** Pede o dia (1 a 31) e "vale a partir de", que vem
  preenchido com o **primeiro dia do mês atual** (o dono vai lançar só compras novas) e editável, com
  a ajuda: "compras anteriores a esta data são recusadas". Se o fechamento for omitido, aviso
  persistente na lista: "sem fechamento, a compra no crédito será recusada". Não há transação única
  (nenhum endpoint novo): se o cartão for criado e o fechamento falhar, a tela diz "cartão criado,
  falta o fechamento" e leva ao `ConfigCartao`.
- **Editar a linha** (nome e limite) com `versao`; o limite novo vale para tudo, inclusive o passado
  (sem vigência por data, registrar a limitação na tela e no ADR).
- **Dívida inicial: começar do zero** (decisão do dono). Sem saldo inicial; um texto curto avisa que
  parcelas antigas ainda em aberto precisam ser lançadas uma a uma, se o dono quiser vê-las.
- O front **não calcula nada** (ADR 015): limite, vigência e erros vêm do servidor.

Fora da task: excluir linha ou cartão (não existe), trocar a linha de um cartão com lançamentos,
vigência por data para o limite, mudar o tipo de uma conta existente, endpoint que crie cartão e
fechamento numa chamada, snapshot de cartão com sinal automático, pagamento de fatura, alertas.

## Acceptance criteria

- [x] SPEC-012-AC-25: a seção "Novo cartão" cria a linha de crédito (nome, limite) e o cartão ligado a ela (envia `linha_credito_id`); nome repetido (409) e mensagens do banco aparecem sem recalcular nada
- [x] SPEC-012-AC-26: o fechamento é pedido junto (dia e "vale a partir de" com o 1º dia do mês atual como padrão, editável); sem fechamento há aviso persistente; falha só do fechamento mostra "cartão criado, falta o fechamento" com acesso ao `ConfigCartao`
- [x] SPEC-012-AC-27: editar a linha (nome e limite) com `versao`; 409 de versão velha mostra "mudou desde a leitura"; a tela informa que o limite novo vale para tudo
- [x] SPEC-012-AC-28: criar outro cartão em linha existente (limite compartilhado) sem oferecer trocar a linha de um cartão existente
- [x] SPEC-012-AC-29: o front não recalcula (limite como texto, respostas incoerentes de propósito) e o tipo cartão não aparece no formulário genérico de Conta; estados de carregando, erro, 401 e vazio tratados
- [x] SPEC-012-AC-30: jornada e2e: criar linha e cartão com fechamento, lançar uma compra no crédito e vê-la na fatura

## Notes

Rascunho de regras e fixtures: F-LIM-01/02 e F-FECH-01/02/03 já cobrem a regra financeira; esta task
não cria regra nova. O teste de recusa de compra sem fechamento vigente já existe no backend (SPEC-005).
