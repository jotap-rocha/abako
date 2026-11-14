# 053 — Tela do vale, bolso no formulário e R5 nos alertas: convenções do front da task 20

**Status:** Aceita
**Data:** 2026-11-13
**Autores:** time
**Reversibilidade:** alta (só front; nenhuma regra nova)

---

## Contexto

O ADR 052 definiu o vale (VR), os bolsos, a sobra e o R5 e a API os entrega prontos. O ADR 023
manda a tela principal nunca mostrar o vale. Faltava decidir detalhes de tela que o ADR 052 não
cobre. Nenhum nome real de emissor entra no repositório (ADR 022): só "VR" e "VA".

## Decisão

1. **Página `/vale`** (item "Vale" no menu) é a única que consulta e mostra o vale. Busca de uma vez
   situação, benefícios, decisões e contas do mês escolhido; o mês corrente é o limite (nunca
   futuro). Tudo é exibido como a API devolveu; o único teste local é o sinal de menos no `resta`,
   só para destacar o estouro (texto "estourado"), sem conta e sem compensar o outro bolso.
2. **Estados:** `sem_conta` mostra o formulário que marca o VR (conta de benefício, base de
   trabalho com sugestão de 200,00, destino padrão, mês de vigência; recusa do banco aparece
   literal). `sem_credito` mostra aviso (sem alerta) e **mantém** os bolsos, o ajuste e o
   consumo, porque a API os calcula nesse estado (ADR 052, decisão 4). Estado desconhecido é
   tratado como `ok`.
3. **Marcação do VR** também fica disponível no estado `ok` ("Marcação do VR"), para trocar base ou
   destino padrão com nova vigência. A vigência é escolhida por mês (`type="month"`) e enviada
   como dia 1.
4. **Decisão da sobra:** seletor e botão habilitados só com `mes_encerrado` verdadeiro (flag da
   API; o front não compara datas). Pré-seleciona a decisão vigente ou, sem ela, o `destino_padrao`.
   Mostra a versão vigente e o histórico de versões do mês. A tela repete que a decisão não move
   saldo.
5. **Benefícios:** VR e VA lado a lado; o VR leva a etiqueta "vale-refeição"; as demais contas
   de benefício levam "sem bolsos". O nome da conta é resolvido no front pela lista de contas.
6. **Bolso no formulário** (regra do banco: bolso obrigatório na despesa da conta VR; opcional na
   despesa de conta de benefício quando nenhum VR está marcado na data, para classificar o
   histórico antes de marcar; proibido nos demais casos). A tela só espelha: o campo aparece (a)
   **obrigatório**, padrão "pessoal", na despesa da conta do VR vigente **no mês corrente**
   (GET `/api/vale/parametro` sem `mes`, buscado junto da lista de lançamentos); (b) **opcional**,
   com a opção "Sem bolso" e o texto "classifique agora se esta conta será o seu VR", na despesa de
   conta de benefício quando esse parâmetro vem nulo (nenhum VR marcado). Não aparece no VA quando
   outra conta é o VR, em conta comum nem na receita. Se a leitura do parâmetro falhar, o campo
   não aparece e o banco decide (422 com a mensagem literal). Limitação aceita: a tela decide pelo
   VR do mês corrente; uma despesa com data de outro mês cuja vigência difere pode ser recusada
   pelo banco, e a mensagem dele explica. Qualquer mudança de campo (inclusive o bolso) gera chave
   de idempotência nova; repetir sem mudar mantém a chave. A lista mostra o bolso do lançamento.
   Marcar o VR com despesas antigas sem bolso é recusado (422): a tela mostra a mensagem literal e
   orienta (abrir os lançamentos, editar cada despesa informando o bolso e marcar de novo), com
   link para `/lancamentos` (a lista ainda não tem filtro por conta).
7. **R5 na tela Alertas:** alerta forte (borda e etiqueta de severidade), com o texto da API, bolso,
   mês, alocação, consumo e resta, e link para o vale. Sem botão de dispensar (alerta existe
   enquanto a condição existe, ADR 049).
8. **R5 fora do Início:** o resumo de alertas do Início **filtra** o R5 (código "R5" ou `vale`
   preenchido). O texto nunca afirma ausência de alertas: lista vazia diz "Nenhum alerta
   neste resumo."; se o filtro descartou algo, mostra também "Há outros alertas." (sem dizer o que
   são); o link para Alertas aparece sempre. O filtro é de **apresentação**, não de segurança:
   `/api/alertas` continua entregando ao navegador os números do vale; o Início só não os exibe
   (nenhum parâmetro novo na API). É seleção de exibição, não regra financeira; quem quer ver o R5 abre Alertas ou a página do vale. O Início
   não chama nenhuma rota do vale e não mostra receita de benefício.
9. **Glossário:** termos `vale`, `bolso`, `resta`, `sobra_vale`, `estouro`, na página do vale e em
   Alertas. A "sobra" do R2 mantém o termo próprio.

## Consequências

- O Início omite o alerta forte R5, mas avisa de forma neutra que há outros alertas e leva a Alertas.
  O ADR 023 prevalece sobre o destaque.
- O front depende de `mes_encerrado`, `estado` e `conta_vr_id` da API; nenhum cálculo novo.

## Alternativas consideradas

- Deixar o R5 no resumo do Início ❌: vazaria o vale para a tela principal.
- Calcular "mês encerrado" no front ❌: regra de data de negócio, é do banco.
- Esconder bolsos em `sem_credito` ❌: a API os calcula e o consumo é informação útil.

## Como verificar

SPEC-013-AC-14 a AC-20; `frontend/src/vale/*.test.tsx`, `tests/e2e/test_vale.py`.

## Impacto em SI/LGPD

Dado financeiro pessoal (ADR 014). A tela só exibe o que a sessão autenticada recebe da API; a
única informação em URL é o mês `AAAA-MM`. Nenhum valor vai a console, log, `localStorage` ou
cache do navegador (o service worker não toca em `/api`). O nome da conta aparece só na tela do
dono. Os dados de teste são sintéticos. Finalidade e minimização inalteradas.
