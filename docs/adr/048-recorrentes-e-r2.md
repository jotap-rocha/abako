# 048 — Recorrentes, vínculo, vencimento do cartão e sobra do R2: convenções da SPEC-010

**Status:** Aceita
**Data:** 2026-11-12
**Autores:** time
**Reversibilidade:** moderada (quatro tabelas, views e funções; o downgrade recusa se houver dados)

---

## Contexto

O ADR 023 definiu o R2 (`sobra = disponível − compromissos`, horizonte inicial de 10 dias) e o
recorrente (nome, tipo, valor esperado, dia, conta, vigência), mas deixou em aberto: o que é uma
ocorrência e como ela se liga a uma transação, de onde vem o dia de vencimento da fatura (o ADR 043
item 2 o adiou para esta SPEC), como a fatura entra na sobra quando já houve pagamento (ADR 044) e
os limites exatos do horizonte. Decisões do usuário em 2026-11-12.

## Decisão

1. **Recorrente** (`recorrente`): nome (1 a 80, único entre os vigentes), tipo `fixo` (despesa
   recorrente) ou `receita`, valor esperado (> 0, 2 casas), dia do mês (1 a 31), conta e vigência
   `mes_inicio` .. `mes_fim` (mês de início obrigatório; fim opcional; ambos inclusivos). Versionado
   como `pessoa` (`versao`, `vigente`, `excluida`): editar cria nova versão, excluir é lógico, o app
   não tem UPDATE/DELETE. **Fixo e receita recorrentes só em conta `corrente`**: assinatura no
   cartão entra como compra normal (parcela), não como recorrente. A edição vale para todas as
   ocorrências **ainda não vinculadas** (as vinculadas guardam o valor da transação). Depois de
   haver vínculo, tipo e conta não mudam e o período não pode deixar vínculo de fora (recusa).
2. **Ocorrência é derivada, não gravada**: uma por mês do período. Data = dia do cadastro, ou o
   **último dia válido** do mês quando o dia não existe (31 em abril é 30; 29 a 31 em fevereiro é
   28, ou 29 em ano bissexto; mesma regra do ADR 027). **Valor = valor esperado até vincular**;
   vinculada, vale o valor absoluto da transação.
3. **Vínculo é fato com histórico** (`recorrente_vinculo`, append-only): cada linha é um evento
   (`recorrente_id`, `mes`, `transacao_id`; `transacao_id` nulo = desvinculou). Vale o último evento
   da ocorrência (view `recorrente_vinculo_vigente`). **Uma transação por ocorrência e uma
   ocorrência por transação**. Escrita só por `recorrente_vincular` e `recorrente_desvincular`
   (recusam transação de outro tipo ou conta, ocorrência já vinculada a outra transação e
   transação já usada em outra ocorrência). O tipo esperado da transação é `debito` para fixo e
   `receita` para receita, **na conta do recorrente**. O vínculo só **conta** (view
   `recorrente_vinculo_efetivo`) enquanto a transação está vigente, não excluída e ainda casa com
   tipo e conta; excluir ou editar a transação para outro tipo ou conta devolve a ocorrência a
   **pendente**, sem apagar o histórico (a mais conservadora: volta a pesar na sobra).
   **Limites aceitos na v1:** (a) o vínculo não exige que a data da transação fique perto da
   data da ocorrência (pagar o aluguel de maio em março vincula igual); (b) **receita recorrente
   não vinculada, cuja transação já foi lançada, conta em dobro** (o saldo já a inclui e a
   ocorrência ainda soma ao disponível): por isso a tela da task 17 deve sugerir vincular. Fixo
   não vinculado já pago tem o mesmo efeito, só que contra o usuário (compromisso em dobro).
4. **Horizonte do R2** (`r2_parametro`, dias de 1 a 90): parâmetro com vigência, append-only como
   o fechamento do cartão (ADR 043 item 5) e a reserva (ADR 047 item 8): vale o de maior
   `vigente_desde` ≤ hoje; no mesmo `vigente_desde`, o último gravado; **inicial 10** quando nada foi
   gravado. O horizonte é **inclusivo**: vão de `hoje` até `hoje + horizonte`, os dois dias dentro
   (com 10 dias e hoje 10/05, a ocorrência de 10/05 e a de 20/05 entram; a de 21/05 não).
5. **Vencimento do cartão** (`cartao_vencimento`, dia 1 a 31, `vigente_desde`): cadastro por cartão
   **com vigência**, como o fechamento, escrita por `vencimento_gravar`. Os dias reais são
   preenchidos pelo usuário no app, nunca no repositório. **Vencimento da competência M**: com os
   dias de fechamento F e de vencimento V **vigentes no último dia de M**, vence no mês M se
   `V > F`; senão, no mês M+1. Dia inexistente no mês usa o último dia do mês.
   **Retroatividade:** para competência **anterior à primeira vigência cadastrada** vale a
   primeira (de fechamento e de vencimento), senão cadastrar o vencimento com `vigente_desde` =
   hoje faria a fatura do mês passado, que vence no horizonte, sumir da sobra. Isso só vale para
   o cálculo do vencimento e do fechamento da fatura no R2; não recalcula a competência de
   compras já feitas (ADR 043 item 5). Cartão com dívida e **sem nenhum** vencimento (ou sem
   nenhum fechamento) cadastrado não entra na sobra e é contado em `pendencias_vencimento`
   (pedido de configuração; a tela avisa). **`vigente_desde` de horizonte e de vencimento não
   passa de 5 anos no futuro** (AB422): uma vigência absurda sombrearia a configuração.
6. **Disponível** = soma do `saldo_derivado` (ADR 041) das contas `corrente` vigentes e não
   excluídas em `hoje` (reserva, investimento, benefício e dívida ficam fora; o crédito do vale
   nunca entra, INV-26) + **receitas recorrentes pendentes** com data em `[hoje, hoje + h]` em
   conta corrente. **Compromissos** = **fixos pendentes** com data em `[hoje, hoje + h]` + **faturas
   próprias** com vencimento em `[hoje, hoje + h]`. **Sobra = disponível − compromissos**; `alerta`
   = sobra < 0 (a rota e a tela do alerta R2 são da task 17; aqui só se calcula).
7. **Ocorrência vinculada sai do cálculo; vencida não vinculada** (data < hoje) vai para uma
   **lista separada** (`grupo = 'vencida'` em `r2_itens`) e **não entra na sobra** (INV-19).
   Ocorrência de hoje ainda não vinculada é pendente (entra). **Só conta como vinculada se a
   transação tem data <= hoje**: vínculo com transação de data futura mantém a ocorrência
   pendente (o saldo ainda não caiu); a lista do mês (`ocorrencias_do_mes`) mostra o vínculo
   real. **Retroatividade das vencidas: 24 meses** a partir de hoje (`hoje − 24 meses`,
   inclusive); ocorrências mais antigas não aparecem na lista, e um recorrente antigo nunca
   vinculado não gera centenas de linhas. A vencida some da lista quando é vinculada ou quando
   o recorrente é editado/excluído.
8. **Fatura própria no R2 desconta o pago já alocado (ADR 044), só o que já saiu da conta.**
   Compromisso da fatura de competência M = `max(fatura própria de M − pago alocado às parcelas
   próprias de M, 0)`. A fatura própria é `fatura_resumo(...).propria` (parcelas sem
   `pessoa_id`, mais o crédito de estorno da compra própria; terceiros fora, INV-18). O pago
   alocado vem de `alocacao_pago_ate(p_user, p_conta, hoje)`, variante do R2 de `alocacao_pago`
   (ordem competência, data da compra, parcela) cujo pool só soma **transferências com data
   <= hoje**; `pool_pago` e `alocacao_pago` do ADR 044 **não mudam**. Pagamento com data futura
   não abate: o saldo (`saldo_derivado` em hoje) também só cai na data, então a sobra não fica
   inflada. O crédito de estorno sempre desconta do pool (menos pago = mais compromisso).
   O pagamento do cartão **não distingue** própria de terceiros (ADR 044 item 1); a alocação
   segue a ordem cronológica das parcelas **dos dois**. Efeito exato (F-R2-12): (a) parcela de
   terceiro **anterior** à própria (mesma competência) absorve o pago antes dela, e o compromisso
   da própria **sobe** (a sobra cai); parcela de terceiro **posterior** não atrapalha;
   (b) competência mais antiga, própria ou de terceiro, ainda não paga absorve o pago primeiro,
   mesmo que já vencida; um pagamento que não a cobre não chega à fatura que vence no horizonte.
   Em nenhum caso o pago pode **diminuir** o compromisso além do que foi alocado às parcelas
   próprias; mas o terceiro anterior pode **aumentar** o compromisso em relação a ratear o
   pago (decisão conservadora aceita). Fatura sem saldo próprio a pagar vale 0 (crédito
   excedente não vira disponível).
9. **Fatura aberta aparece como parcial**: a fatura de M está aberta enquanto `hoje` é anterior ao
   dia de fechamento efetivo de M (compra no dia do fechamento vai para a seguinte, ADR 043 item 1);
   o item sai com `parcial = true` e entra na sobra com o valor até agora. Faturas com vencimento
   já passado (`< hoje`) e ainda em aberto não entram na sobra nem nas vencidas (fora de escopo; o
   saldo da dívida já aparece no limite).
10. **Escrita só por função** (`SECURITY DEFINER`, `search_path` fixo, `EXECUTE` só para
    `abako_app`): `recorrente_gravar`, `recorrente_excluir`, `recorrente_vincular`,
    `recorrente_desvincular`, `r2_parametro_gravar`, `vencimento_gravar`. Erros `AB404`, `AB409`,
    `AB410`, `AB422` com **mensagem literal** (sem `||`, teste estático).
11. **Leituras `INVOKER` com `p_user` e `p_hoje`** (INV-13; a data é parâmetro por determinismo, a
    API passa a data civil de `America/Sao_Paulo`): `ocorrencias_do_mes(p_user, 'AAAA-MM')`,
    `vencimento_fatura`, `fatura_fechamento`, `r2_horizonte`, `r2_itens` (grupos `receita`, `fixo`,
    `fatura`, `vencida`; item com data, valor, bruto, pago e `parcial`) e `r2_situacao` (uma linha:
    `horizonte_dias`, `data_fim`, `saldos_correntes`, `receitas_pendentes`, `disponivel`,
    `fixos_pendentes`, `faturas_proprias`, `compromissos`, `sobra`, `alerta`, `vencidas`,
    `pendencias_vencimento`). Helpers puros: `data_no_mes`, `meses_entre`.
12. **Papéis:** `abako_app` executa as funções e lê tabelas e views; `abako_pipeline` só
    `SELECT` nas tabelas de **configuração** (`r2_parametro`, `cartao_vencimento` e as views de
    vigência), sem `EXECUTE`. **O pipeline não lê `recorrente` nem `recorrente_vinculo`**: o
    nome é texto livre e valor, dia, conta e histórico de pagamento de cada recorrente
    identificam hábitos do usuário; o analítico só ganha acesso quando a SPEC-014 definir a
    agregação de que precisa (minimização, LGPD art. 6).

## Consequências

- Migração 0011: quatro tabelas (`recorrente`, `recorrente_vinculo`, `r2_parametro`,
  `cartao_vencimento`), views de vigência e de vínculo efetivo e as funções acima. O downgrade
  recusa se houver dados nas quatro tabelas.
- A sobra reaproveita `saldo_derivado`, `fatura_resumo`, `alocacao_pago` e `parcela_ativa`: nenhuma
  regra de fatura, pagamento ou terceiros foi reescrita.
- Pendente de API (fin-backend): rotas de recorrentes (CRUD, vincular, desvincular, ocorrências do
  mês), do horizonte e do vencimento do cartão (leitura e gravação) e da situação do R2 com `hoje`
  em `America/Sao_Paulo`; dinheiro em texto; `user_id` da sessão; valores fora do log. O alerta
  (task 17) decide a partir de `alerta`. O front só exibe (ADR 015).

## Alternativas consideradas

- Ocorrência gravada mês a mês ❌: exigiria rotina de geração e UPDATE; derivar é determinístico.
- Vínculo como coluna da transação ❌: a transação não sabe do recorrente; o fato é do vínculo.
- Vínculo editável por UPDATE ❌: perde histórico e o app não atualiza tabelas de versão.
- Contar a vencida na sobra ❌: o ADR 023 manda listar à parte; contar dobraria o que já saiu.
- Fatura própria pelo total sem descontar o pago ❌: conta em duplicidade o dinheiro que já saiu
  da conta (o saldo já caiu).
- Contar pagamento de data futura ❌: o saldo ainda não caiu e a sobra sairia inflada.
- Alterar `alocacao_pago` do ADR 044 com `p_hoje` ❌: mudaria estorno e edição; o R2 tem a variante dele.
- Pagamento alocado só a parcelas próprias ❌: o pagamento não distingue; inventaria um vínculo
  que o ADR 044 recusou.
- Dia de vencimento fixo no repositório ❌: dado pessoal do usuário (ADR 022).

## Fora de escopo

Rota, tela e alerta R2 (task 17); fatura vencida em aberto como pendência; projeção além do
horizonte; recorrente em cartão; categoria; agregação no analítico (SPEC-014).

## Como verificar

INV-18, INV-19, INV-26; fixtures F-R2-01 a F-R2-15 e F-FECH/F-FAT; critérios SPEC-010-AC-1 a AC-13;
`tests/db/test_r2.py` (inclui F-R2-12 a F-R2-15), `test_recorrente.py`, `test_r2_propriedades.py`, `test_r2_mensagens.py`,
`test_migracao_0011.py`, `test_papeis.py`.

## Impacto em SI/LGPD

Dado financeiro pessoal (ADR 014). As quatro tabelas têm `user_id`; a escrita só passa pelas
funções `SECURITY DEFINER`, que recebem o `user_id` da sessão (INV-13), e o app não tem
`INSERT/UPDATE/DELETE` direto. As leituras filtram por `p_user`: com o `user_id` de outro usuário
devolvem zero/vazio. O nome do recorrente é texto livre do usuário e pode identificar um serviço
ou um contrato: o pipeline não tem `SELECT` nessa coluna, e nenhum nome, valor ou id entra em
mensagem de erro, log, URL ou serviço externo. Dias de fechamento e de vencimento reais ficam só no
banco do usuário, nunca no repositório. Finalidade e minimização inalteradas.

**Risco residual aceito:** as funções recebem `p_user` por parâmetro e não há RLS, como nas
migrações 0006 a 0010; a v1 é de um único usuário e o isolamento depende de a API passar o
`user_id` da sessão (INV-13). Revisar se o produto virar multiusuário.
