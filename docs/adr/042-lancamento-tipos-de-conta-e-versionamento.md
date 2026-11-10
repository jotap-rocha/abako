# 042 — Lançamento por tipo, tipos de conta e escrita versionada por função (SPEC-004)

**Status:** Aceita
**Data:** 2026-11-09
**Autores:** time
**Reversibilidade:** difícil

---

## Contexto

A SPEC-004 lança os sete tipos do ADR 011, edita criando versão, exclui logicamente e protege
contra duplicidade e edição concorrente (ADR 029). O esquema da 0002 só tinha conta, data, valor e
descrição; a conta só tinha nome e "é benefício". O ADR 036 deixou para cá a troca de vigência
(o papel `abako_app` não tem UPDATE). Decisões do usuário em 2026-11-09: crédito e repasse ficam
recusados até as SPECs deles; data futura é recusada; chave de idempotência repetida com dados
diferentes é erro; tipos de conta entram já, com edição de conta; a "caixinha"/"cofre" do banco é
uma reserva que **pertence ao banco**, mas tem saldo próprio e nunca se mistura à conta corrente.

## Decisão

### Tipos de conta

- `conta_versao.tipo`: `corrente | reserva | investimento | beneficio` (dívida/cartão entra na
  SPEC-005). `conta_beneficio` continua, derivada: `conta_beneficio = (tipo = 'beneficio')`.
- `conta_versao.conta_mae_id` (opcional, só para `reserva`/`investimento`): a conta corrente do
  mesmo banco. É a caixinha/cofre: saldo e snapshot próprios, fora do saldo da corrente e do
  disponível do R2. O nome é livre (cada banco chama de um jeito; não há mapeamento por banco).
- A 0005 preenche `tipo` das contas existentes: `beneficio` se marcada, senão `corrente`.
- Editar conta (nome, tipo, conta-mãe) cria nova versão, com o mesmo controle de versão das
  transações.

### Lançamento

- `transacao_versao` ganha `tipo` (os sete do ADR 011), `perna` (1 ou 2), `bruto` e `imposto`
  (só rendimento) e `hash_corpo` (idempotência). Um lançamento é um `transacao_id` lógico; a
  transferência e o investimento têm **duas linhas (pernas) com o mesmo `transacao_id` e a mesma
  `versao`**, uma em cada conta, soma zero (INV-01). Unicidades passam a incluir `perna`.
- **Valor:** a API recebe sempre positivo; o sinal vem do tipo, no banco: débito −; receita +;
  transferência/investimento: perna 1 − na origem, perna 2 + no destino; rendimento + (bruto −
  imposto, com `CHECK valor = bruto − imposto`, `bruto > 0`, `0 ≤ imposto < bruto`, INV-36).
- **Regras de aceite:** crédito e repasse são recusados (chegam com SPEC-005 e SPEC-007);
  transferência exige contas diferentes e nenhuma de benefício (o vale é da SPEC-013);
  investimento exige destino do tipo `investimento`; rendimento não cai em conta de benefício;
  data entre 2000-01-01 e hoje (America/Sao_Paulo), sem futuro.
- **Escrita só por função.** `lancamento_gravar(...)` e `conta_gravar(...)`, `SECURITY DEFINER`
  do dono, com `search_path` fixo e `EXECUTE` só para `abako_app`, validam, fecham a versão
  vigente (`vigente = false`) e inserem a nova numa única transação. **`abako_app` perde o INSERT
  direto em `conta_versao` e `transacao_versao` e o USAGE das sequências de id**: não existe outro
  caminho de escrita. Isso altera o ADR 036.
- **INV-01 no esquema:** além dos CHECKs por linha, uma trigger de constraint adiada confere, no
  commit, cada versão gravada: 1 perna (2 em transferência/investimento, contas diferentes, soma
  zero), com o mesmo tipo, data e marca de exclusão. Vale até para o dono do banco.
- **Conflito (INV-29):** editar ou excluir (lançamento ou conta) exige a `versao` vigente;
  diferente → 409, nada gravado. A troca acontece com a linha travada: duas edições simultâneas
  não passam juntas, e a que esperou a trava recebe 409 (não 404). As contas lidas por um
  lançamento ficam com `FOR SHARE` até o fim, para não mudarem de tipo no meio.
- **Exclusão lógica:** nova versão vigente com `excluida = true`. Não há "desexcluir" na v1:
  editar ou excluir um lançamento excluído responde 404.
- **Idempotência (INV-28):** a chave fica na perna 1 da versão 1, com o hash (SHA-256) do corpo
  canônico. Mesma chave e mesmo corpo → devolve o lançamento original, sem criar outro; mesma
  chave e corpo diferente → 422. Uma trava por (usuário, chave) faz a repetição simultânea
  esperar a primeira e devolver o original. A chave de um lançamento já excluído responde 409.
- **Erros do banco** usam SQLSTATE próprios (`AB404`, `AB409`, `AB410` nome de conta repetido,
  `AB422`) que a API traduz em HTTP; a mensagem é curta e sem dado financeiro, e o código vai no
  cabeçalho `X-Abako-Erro` para o front distinguir os dois 409 sem depender do texto.
- `criado_em` de cada versão é o `recorded_at` do ADR 026.

## Alternativas consideradas

- Pernas com `transacao_id` diferentes ligadas por um id de grupo: duas versões e duas chaves para
  um mesmo lançamento ❌.
- Função que só fecha a versão e INSERT direto pela aplicação: permitiria fechar sem substituir
  ou gravar perna solta ❌.
- Usuário digita o valor com sinal: regra no front e erro fácil ❌ (ADR 015).
- Caixinha como parte do saldo da conta do banco: mistura reserva e dinheiro disponível ❌.
- Devolver o original para chave repetida com corpo diferente: esconde erro do cliente ❌.

## Consequências

- O teste de papéis da SPEC-001 muda: `abako_app` não insere mais nas tabelas de versão.
- Categoria, estabelecimento, grupo e pessoa (ADR 011/012) ficam para quando alguma regra
  precisar deles; parcelas, fatura e crédito na SPEC-005; repasse e pessoa na SPEC-007.
- A 0005 em `prd` atualiza o `tipo` das contas existentes (dado do usuário): exige backup e aval.
  Fora do `tst` ela aborta se já houver lançamentos (o tipo deles seria deduzido do sinal).
- **A 0005 é irreversível com dados:** o downgrade se recusa se houver perna 2, tipo novo de
  lançamento ou conta reserva/investimento/com banco. Voltar exige restaurar o backup anterior.
- "O imposto não é gasto real" (INV-36) foi para o INV-04, testado na SPEC-008 (gasto real).

## Como verificar

`tests/db/test_transferencia.py`, `test_versionamento.py`, `test_exclusao.py`,
`test_rendimento.py`, `test_lancamento_regras.py`, `test_conta_versao.py`, `test_papeis.py`,
`test_migracao_0005.py`;
`tests/backend/test_lancamentos_api.py`, `test_idempotencia.py`, `test_conflito.py`; fixtures
F-TRANSF-01, F-REND-01.

## Impacto em SI/LGPD

Reduz superfície: a aplicação deixa de inserir direto nas tabelas de versão. As funções recebem o
`user_id` da sessão (INV-13), validam que contas e lançamentos são do mesmo usuário e nunca
registram valores em log.
