# 052 — Vale (VR) com bolsos, sobra com decisão e alerta R5: convenções da SPEC-013

**Status:** Aceita
**Data:** 2026-11-13
**Autores:** time
**Reversibilidade:** média (três tabelas novas e uma função de escrita com parâmetro novo; o downgrade recusa se houver dado)

---

## Contexto

O ADR 023 definiu o vale (item 6 e 7) e o R5 como "conta de benefício única", sem dizer qual conta
é a de refeição, onde o bolso é gravado, como a decisão da sobra se encadeia entre meses nem o que
acontece com o mês sem crédito. O usuário tem duas contas de benefício: o vale-refeição (**VR**) e o
vale-alimentação (**VA**). Decisões do usuário em 2026-11-13: só o VR tem bolsos (trabalho/pessoal),
sobra e R5; o VA é outra conta de benefício, sem bolsos, também fora do gasto real, e entra na
receita total e na página de benefícios. A tela principal nunca mostra o vale. Este ADR só detalha a
modelagem; ele não reabre essas decisões. Nenhum nome real de emissor entra no repositório (ADR 022):
só "VR" e "VA".

## Decisão

1. **Marcação da conta VR, versionada por mês.** Tabela append-only `vale_parametro` (conta do VR,
   base de trabalho, destino padrão, `vigente_desde`), no molde de `reserva_parametro` e
   `r2_parametro`: nada é atualizado nem apagado; para a mesma vigência vale o último gravado
   (`vale_parametro_vigente`). A vigência é **sempre o dia 1 de um mês** (o vale é mensal; assim
   uma despesa e um mês escolhem o mesmo parâmetro: o de maior `vigente_desde` menor ou igual à
   data). Escrita só por `vale_parametro_gravar` (`SECURITY DEFINER`, `search_path` fixo), que exige
   conta **vigente, não excluída, do usuário e do tipo `beneficio`**. Depois de gravar a vigência,
   recusa (AB422, e o INSERT é desfeito) se a conta tiver despesa vigente **sem bolso nos meses em
   que ela passa a ser o VR** (olha só os meses em que `vale_conta_em` devolve esta conta, então
   uma vigência posterior de outra conta não gera recusa espúria); a mensagem orienta a editar as
   despesas antigas informando o bolso e marcar depois (item 3). Sem
   parâmetro: nenhuma conta é VR, o estado do vale é `sem_conta` e ninguém precisa de bolso.
2. **Base de trabalho:** R$ 200,00 inicial, mas **só vale depois de gravada** no parâmetro (junto
   da conta); alterá-la é gravar nova vigência (a base antiga continua valendo nos meses antigos).
3. **Bolso da despesa.** Tabela append-only `vale_bolso (user_id, transacao_id, versao, bolso)`,
   escrita só por `lancamento_gravar`, que ganha o 16º parâmetro `p_bolso text DEFAULT NULL`
   (quem chamava com 15 argumentos continua funcionando; o guarda do estorno do ADR 044 segue na
   frente). Regra para uma despesa (`debito`) na data da despesa:
   - na conta que é o VR marcado nessa data: `p_bolso` **obrigatório** (`trabalho` ou `pessoal`);
   - em conta de **benefício quando nenhum VR está marcado** nessa data: `p_bolso` **opcional**
     (permite classificar o histórico ANTES de marcar o VR; sem isso quem já tem gastos ficaria
     sem saída, pois a marcação exige as despesas classificadas);
   - em qualquer outro caso (conta que não é de benefício; o VA ou outra conta de benefício
     quando OUTRA conta é o VR na data; receita): `p_bolso` **proibido**. O VA continua sem
     bolsos.
   Valor de bolso diferente de `trabalho`/`pessoal` é recusado. Editar a despesa exige informar o
   bolso de novo (nova versão, nova linha de bolso); excluir é a exclusão lógica de sempre. O
   padrão "pessoal" é só sugestão da tela. Conta ausente (`NULL`) é "conta não encontrada", não
   erro de bolso. **Trava:** `lancamento_gravar` (despesa ou bolso informado) e
   `vale_parametro_gravar` tomam, nesta ordem e antes de qualquer outra, a mesma trava de
   usuário (`pg_advisory_xact_lock`); a de `cartao_trava` (ADR 044) vem depois, sem deadlock. Assim
   marcar o VR e lançar uma despesa do mesmo usuário se serializam: a despesa sem bolso que
   chegou antes é vista pela marcação, e a que chega depois já vê o VR.
4. **Cálculo do mês** (função de leitura `INVOKER`, `vale_calculo`, composta por `vale_situacao`):
   - **crédito** = receitas vigentes lançadas na conta VR no mês civil;
   - **alocação inicial**: `trabalho = min(base, crédito)`, `pessoal = max(crédito − base, 0)`;
   - **ajuste** = a sobra do mês anterior, **inteira**, no bolso escolhido na decisão daquele mês
     (decisão `nenhum` ou ausente: ajuste zero);
   - **alocação efetiva** = alocação inicial + ajuste; **consumo** = despesas vigentes do VR no mês
     por bolso; **resta** = alocação efetiva − consumo (pode ser negativo);
   - **sobra** = Σ max(resta, 0) por bolso, **sem compensar** estouro de um bolso com sobra do
     outro (INV-25);
   - **cálculo iterativo** (`vale_mes` por mês + `vale_calculo` que volta ao início da cadeia de
     decisões e avança), sem recursão: uma cadeia de centenas de meses não estoura a pilha;
   - **não acumula**: o resto de um mês só chega ao seguinte pelo ajuste decidido (INV-21); o
     ajuste usa a sobra **recalculada** do mês anterior (a decisão guarda o destino, não o valor);
   - **estado**: `sem_conta` (nenhum VR vigente no mês), `sem_credito` (crédito zero ou ausente) ou
     `ok`. Em `sem_credito` o resta continua calculado (consumo e ajuste aparecem), mas **não
     dispara R5**.
5. **Decisão da sobra** = evento com histórico: tabela append-only `vale_decisao (user_id, mes,
   destino, versao)`; nova decisão do mesmo mês é uma **nova versão** que substitui a anterior
   (`vale_decisao_vigente`); o histórico fica na tabela. Destino **único** (`trabalho`, `pessoal`
   ou `nenhum`) que recebe a sobra inteira. Só se decide sobre mês **encerrado** (anterior ao mês
   civil de hoje em `America/Sao_Paulo`) e com VR vigente no mês. Repetir o destino vigente não cria
   versão. O destino padrão do parâmetro só **pré-seleciona** a tela: sem decisão gravada, sem
   ajuste. A decisão **nunca move saldo** (INV-25): não grava transação nem snapshot; só muda a
   alocação efetiva do mês seguinte.
6. **Saldo total do VR** = `saldo_derivado` normal da conta (acumula), conferido por snapshot; a
   divergência continua sendo o R4 (INV-22, INV-23).
7. **VA e receita total.** `beneficios_contas(p_user, p_mes, p_hoje)` lista as contas de benefício
   vigentes (VR e VA) com receita e despesa do mês e saldo; a marca `vale_refeicao` diz qual é o
   VR. `receita_total = receita_caixa + receita_beneficio` (ADR 046) já soma qualquer conta de
   benefício, então o VA entra sem mudança; o gasto real continua excluindo as duas.
8. **R5 em `alertas`** (nova versão da função, mesma assinatura, cinco colunas novas no fim:
   `bolso`, `alocacao`, `consumo`, `resta`, `mes`): para o **mês corrente** de `p_hoje` e estado
   `ok`, uma linha por bolso com `resta < 0` estrito: `R5`, tipo `alerta`, **severidade `alta`**
   (o excesso já aconteceu e o bolso tem destino próprio; fica no mesmo nível do R2 negativo),
   detalhe `vale_trabalho_estourado` ou `vale_pessoal_estourado`, mensagem literal sem valores. Os
   números vão nas colunas; `conta_id` é o VR. Meses encerrados não alertam (a sobra/estouro deles
   aparece na página do vale); mês sem crédito não alerta; um bolso não compensa o outro.
9. **Relógios e conta excluída.** O `PUT` da decisão usa o `now()` do banco em
   `America/Sao_Paulo` para saber se o mês está encerrado; o `GET` usa o `hoje` injetado (data
   civil de São Paulo calculada pela API). Perto da virada do mês os dois podem divergir por
   instantes (o `GET` mostrar "encerrado" e o `PUT` ainda recusar, ou o contrário); é aceito:
   o banco manda e a recusa é literal (AB422). Se a conta VR for **excluída** (ou deixar de ser
   de benefício), todos os meses que ela cobre viram `sem_conta` (a leitura confere a conta a
   cada consulta); os bolsos e decisões gravados permanecem, e voltam a valer se uma nova
   vigência marcar uma conta válida.
10. **API (task 20, parte seguinte):** o `user_id` vem da sessão (INV-13); dinheiro em texto;
   `hoje` injetável como nos demais; a tela principal nunca consulta o vale.
11. **Papéis:** o `abako_app` lê as tabelas novas (`SELECT`) e executa as funções; a escrita é só
    pelas funções `SECURITY DEFINER`. O `abako_pipeline` não recebe `SELECT` nem `EXECUTE` de nada
    novo. Mensagens de erro são literais (sem `||`, sem valor, nome ou id).
12. **Downgrade:** recusa com mensagem se houver linha em `vale_parametro`, `vale_decisao` ou
    `vale_bolso`; sem dado, devolve `alertas` e `lancamento_gravar` às definições da 0012 e da 0008.

## Consequências

- Migração 0013 (SQL puro, ADR 025), só aplicada em `tst` pelo agente; no `prd` é do usuário, após
  backup (ADR 019).
- Despesa antiga em conta que vira VR precisa de bolso antes de gravar o parâmetro (decisões 1 e
  3): a tela da despesa mostra o campo Bolso também para conta de benefício sem VR marcado.
- A tela do vale (task 20, front) só exibe; nada de min/max no front (ADR 015).
- O "vale" da v1 é o VR; um segundo vale com bolsos exigiria múltiplas contas por vigência.

## Alternativas consideradas

- Coluna `bolso` em `transacao_versao` ❌: obrigaria reescrever `lancamento_gravar_base`, o gatilho
  de pernas, a exclusão e as views; a tabela lateral tem a mesma garantia (por versão) sem tocar
  na função mais crítica.
- Atributo "é VR" na conta ❌: a conta é versionada pelo ledger e a marcação precisa de vigência e
  de base; o parâmetro já é o padrão do projeto.
- Gravar o valor da sobra na decisão ❌: congelaria um número que muda com edição retroativa.
- Acumular o resta entre meses ❌: contraria INV-21.
- Alertar mês sem crédito ❌: sem alocação não há orçamento a estourar (decisão do usuário).
- Compensar estouro com a sobra do outro bolso ❌ (ADR 023 opção C).

## Fora de escopo

Tela e API (partes seguintes da task 20); segundo vale com bolsos; categorização do essencial pago
pelo vale; transferência com conta de benefício (continua recusada, ADR 042).

## Como verificar

INV-20, INV-21, INV-22, INV-24, INV-25; fixtures F-VALE-01 a F-VALE-12; critérios
SPEC-013-AC-1 a AC-14; `tests/db/test_vale.py`, `test_vale_alertas.py`,
`test_vale_propriedades.py`, `test_vale_historico.py`, `test_vale_mensagens.py`, `test_migracao_0013.py`, `test_papeis.py`.

## Impacto em SI/LGPD

Dado financeiro pessoal (ADR 014). Três tabelas novas guardam só ids, datas, texto de domínio
(`trabalho`, `pessoal`, `nenhum`) e valores monetários da base; todas têm `user_id`, e toda função
filtra por `p_user`, que a API recebe da sessão (INV-13); com o `user_id` de outro usuário nada do
primeiro aparece. Nenhum nome de conta, de emissor ou de pessoa entra em tabela, mensagem, log ou
URL (a conta aparece só como `conta_id`; o nome é resolvido na tela). Mensagens são literais. O
pipeline e o analítico não recebem nenhuma das tabelas novas. Finalidade e minimização inalteradas.

**Risco residual aceito:** como nas migrações 0006 a 0012, as funções recebem `p_user` por parâmetro
e não há RLS; a v1 é de um único usuário. Revisar se o produto virar multiusuário.
