# 051 — Formulários restantes: convenções da task 19 (SPEC-012)

**Status:** Aceita
**Data:** 2026-11-12
**Autores:** time
**Reversibilidade:** alta (só telas e uma camada de API do front; sem tabela, migração nem mudança de contrato)

---

## Contexto

As tasks 12 a 18 entregaram a casca, contas, lançamento (cinco tipos) e as telas de leitura. A
task 19 fecha a SPEC-012 com os formulários que faltavam: estorno, pessoas e repasse, recorrentes,
fechamento e vencimento do cartão, e parâmetros (meta da reserva e horizonte do R2). O ADR 015
proíbe regra de cálculo no front; os ADR 011, 013, 030, 043, 044, 045, 047 e 048 definem o que o
servidor faz; o ADR 050 define a exceção do nome de pessoa. Faltavam decisões de tela que o
usuário pode querer contestar. O backend já tinha todas as rotas: nada mudou nele.

## Decisão

1. **Escrita tipada, com o código do servidor.** `frontend/src/api/escrita.ts` traduz o status em
   `ok`, `sessao_expirada` (401), `nao_encontrado` (404), `desatualizado` (409 com `X-Abako-Erro:
   AB409`, "mudou desde a leitura"), `conflito` (409 AB410: nome repetido, vínculo já usado,
   compra já estornada), `invalido` (422 AB422, com o `detail` literal do banco) e `erro` (rede ou
   500). Os dois 409 se distinguem **só pelo cabeçalho**, nunca pelo texto. Sem cabeçalho, 409 vale
   `desatualizado` (o caminho seguro é recarregar). Escrita nunca é repetida sozinha.
2. **Versão otimista em toda edição e exclusão.** A tela guarda a `versao` lida ao abrir a edição,
   a confirmação ou o painel de estorno e envia essa, mesmo que a lista seja atualizada por baixo
   (INV-29). Com `desatualizado`, a tela explica, fecha a edição e busca a lista de novo.
3. **Estorno (ADR 044).** Botão "Estornar" só na compra a crédito que não é, ela mesma, um estorno.
   Antes de enviar, as regras aparecem em texto fixo (compra inteira; integral devolve o limite e
   não mexe na conta corrente; com parte paga, a parte paga vira crédito na próxima fatura aberta;
   cartão imutável depois; compra com parte paga não se edita nem exclui). O resultado mostra os
   quatro valores da API. **A única decisão feita no front** é classificar o texto: `pago` igual a
   zero (`"0.00"`) é "estorno integral"; qualquer outro é "com parcelas pagas". É só para escolher a
   explicação; o front não calcula quanto foi pago, nem o limite devolvido. A API não tem chave de
   idempotência no estorno: em falha de rede a tela manda conferir a lista antes de tentar de novo
   (um segundo envio de estorno já feito volta 409 AB410 "já estornada", sem duplicar). O painel
   ignora um segundo envio enquanto o primeiro está em voo (guarda com `useRef`, não só o botão
   desabilitado). `estornoIntegral` é uma regex sobre o texto (aceita "0", "0.0", "0.00", "0.0000"
   e "-0.00"), sem aritmética.
   Linha de estorno na lista não tem Editar nem Excluir (o cartão fica imutável).
4. **Crédito e repasse saem do "em breve".** Crédito: só contas do tipo dívida (cartão), parcelas de
   1 a 48 (escolhidas numa lista, sem converter texto), o valor é o **total** da compra e a pessoa é
   opcional (vazio = compra própria). Repasse: só conta corrente (nunca benefício, investimento ou
   cartão), pessoa obrigatória, validada na tela com foco no campo. **Não existe campo de divisão**:
   a compra é 100% própria ou 100% de uma pessoa (ADR 030/045, INV-32); o corpo enviado só tem
   campos conhecidos. Os demais tipos deixam de oferecer o cartão como conta de origem (o servidor
   já recusava). O destino da transferência continua aceitando o cartão (pagar fatura é transferência,
   ADR 044). Tudo isso é filtro de apresentação; quem decide é o servidor. A chave de idempotência do
   formulário é **trocada a cada mudança de campo** (pessoa, valor, parcelas, tipo...): chave
   repetida com dados diferentes faria o servidor devolver o lançamento antigo como "repetido".
   Sem mudança nenhuma, o retry mantém a mesma chave (INV-28). Se a lista de pessoas não carregou,
   a lista de lançamentos escreve "pessoa" (neutro) em vez de "pessoa removida".
5. **Pessoas** (`/pessoas`): cadastro, renomear (com versão), excluir (com confirmação; o banco recusa
   se houver compra ou repasse vigente, e a mensagem literal aparece) e lista de "a receber"
   (dívida, repassado, a receber, crédito) exatamente como a API devolve, juntando `/pessoas` (versão)
   com `/pessoas/a-receber` (valores) por `pessoa_id`. Nome repetido (AB410) é explicado no campo.
6. **Recorrentes** (`/recorrentes`): cadastro (nome sem caractere de controle, tipo fixo ou receita,
   valor em texto, dia 1 a 31, conta corrente que não seja benefício, mês de início e fim opcional),
   edição e exclusão com versão, e ocorrências do mês com vínculo e desvínculo. **"Vencida" vem do
   servidor**: a tela cruza a ocorrência com os itens `vencida` de `/api/r2` (mesmo recorrente e
   mesma data) e mostra a contagem `vencidas`; o front não compara data com hoje. Candidatas ao
   vínculo são os lançamentos da mesma conta, no mesmo mês, que não sejam estorno; o servidor confere
   tipo e conta de verdade e a recusa aparece. O campo de mês usa `type="month"` (Chrome desktop). Se a lista de lançamentos chega ao teto de
   200, a tela avisa que pode haver lançamentos mais antigos fora dela.
7. **Fechamento e vencimento do cartão** ficam na página Cartões, abaixo da fatura: histórico de
   vigências (mais recente primeiro) e formulário com dia (1 a 31) e "vigente desde". A tela explica
   que dia inexistente no mês usa o último dia do mês (ADR 027) e que mudar o fechamento não
   recalcula compras já feitas (ADR 043). Depois de gravar, a fatura é buscada de novo (a situação
   aberta/fechada pode mudar).
8. **Parâmetros** (`/parametros`, o destino do link "Configurar a reserva", ADR 050 item 6): meta da
   reserva (meses 1 a 120, gasto essencial em texto, data-alvo opcional, vigente desde) e horizonte do
   R2 (dias 1 a 90, vigente desde), cada um com o histórico de vigências. O formulário parte da
   **última vigência cadastrada** (a API não diz qual está em vigor hoje); mudar é gravar uma nova
   vigência. Os intervalos 1 a 120 e 1 a 90 repetem o que o banco exige, só para avisar antes de
   enviar; o banco continua sendo a autoridade (AB422 aparece literal).
9. **Acessibilidade.** `useErroDeFormulario` liga o erro ao campo (`aria-invalid`,
   `aria-describedby`) e leva o foco ao primeiro campo com problema; erros de formulário usam
   `role="alert"`. `ConfirmarExclusao` põe o foco em "Cancelar". Todo botão de ação em lista tem
   `aria-label` com o item. Tudo alcançável por teclado.
10. **Sem dado em storage, URL ou console.** Um teste varre o código do app e falha se achar
    `localStorage`, `sessionStorage`, `indexedDB`, `document.cookie` ou `console.`. Nome de pessoa
    aparece em claro só na tela do dono (exceção do ADR 050) e vai a nenhum lugar fora dela.
11. **PWA sem mudança de código.** `sw.js` já guarda só a casca pública e deixa `/api` e as telas
    para a rede; o logout apaga todos os caches. O que faltava era prova: `Pwa.test.ts` cobre
    manifesto e ícones (instalável), a lista fechada do service worker (inclusive com cabeçalho de
    autorização), a limpeza no logout e a varredura do item 10.
12. **Infra de teste e de tela.** `useCarga` ganha `atualizar` (busca de novo sem trocar a tela por
    "carregando", para o que o usuário digitou e a mensagem de sucesso não sumirem). O tempo máximo
    de cada teste do Vitest (`testTimeout` em `frontend/vite.config.ts`) subiu de 5 s para 20 s
    porque, nas primeiras rodadas, `sem_regra_no_front` e testes de edição estouraram 5 s com os
    arquivos em paralelo (e com o `check` em andamento ao lado). **Evidência medida depois**
    (127 testes, 22 arquivos): com `--testTimeout=5000` a suíte inteira passou (0 falhas), e o teste
    mais lento levou 2,2 s em paralelo contra 1,1 s com um arquivo por vez. Somas por arquivo,
    paralelo contra sequencial: Leitura 8,2 s contra 2,9 s; Terceiros 6,1 s contra 3,4 s;
    Recorrentes 6,0 s contra 2,8 s; Lancamentos 5,0 s contra 2,1 s. Ou seja, o 20 s é folga contra
    máquina carregada, não uma necessidade medida hoje; manter ou voltar a 5 s é decisão do dono.
    **Decisão do dono (2026-11-13): manter 20 s.**
    O menu lateral passa de 8 para 11 itens (Pessoas,
    Recorrentes, Parâmetros); em tela estreita a barra de baixo fica apertada e o design final decide.

## Dívidas registradas

- O estorno não tem chave de idempotência; a proteção é o 409 "já estornada" do servidor.
- "Estorno integral" depende de o texto de `pago` ser zero. O ideal é a API expor um campo `tipo`
  (`integral` ou `com_pago`); fica para a próxima SPEC que tocar o estorno.
- Os candidatos de vínculo vêm de `GET /api/lancamentos` (limite padrão de 200); lançamentos mais
  antigos podem não aparecer na lista. Uma consulta por mês e conta seria melhor.
- A lista de "vencidas" só enxerga o que `/api/r2` enxerga (a janela do horizonte e o passado que o
  servidor considerar).
- Sem "desfazer" de estorno nem de vínculo além do desvincular (ADR 044).

## Alternativas consideradas

- Calcular "integral" comparando `pago` com `total` no front ❌ (regra no front, ADR 015).
- Oferecer rateio na compra de terceiro ❌ (ADR 030/045, INV-32).
- Calcular "vencida" no front (data da ocorrência menor que hoje) ❌ (regra no front; o servidor já diz).
- Um único formulário genérico de "vigência" para tudo ❌ (reserva tem mais campos; só fechamento e
  vencimento compartilham o componente).

## Consequências

- Nenhuma mudança no backend, no contrato OpenAPI ou no cliente gerado.
- Seis áreas novas no front (`estorno/`, `terceiros/`, `recorrentes/`, `cartao/`, `parametros/`, e a
  camada `api/escrita.ts`), cada uma com testes de componente e duas jornadas Playwright.
- Critérios SPEC-012-AC-15 a AC-24 em `tests/contracts/criterios.yaml` (a task 18 já usava AC-12 a 14).

## Como verificar

`frontend/src/estorno/Estorno.test.tsx`, `frontend/src/terceiros/Terceiros.test.tsx`,
`frontend/src/recorrentes/Recorrentes.test.tsx`, `frontend/src/cartao/ConfigCartao.test.tsx`,
`frontend/src/parametros/Parametros.test.tsx`, `frontend/src/api/escrita.test.ts`,
`frontend/src/pwa/Pwa.test.ts`, `tests/e2e/test_formularios.py`.

## Impacto em SI/LGPD

Nenhum dado novo é coletado ou guardado. Os formulários enviam dado financeiro e nome de terceiro
só para a API do próprio usuário, na sessão autenticada; o `user_id` vem da sessão (INV-13), nunca
do corpo. O nome da pessoa segue a exceção do ADR 050 (em claro só na tela do dono) e o teste do
item 10 impede storage do navegador, cookie manual e `console`. Mensagens de erro do banco são
literais e sem valores. Nada vai a URL (ids numéricos nos caminhos; mês e versão em query não
identificam pessoa) nem a cache (o service worker não toca na API, provado por teste).
