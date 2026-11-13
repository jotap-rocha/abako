# 050 — Telas de leitura: convenções da task 18 (SPEC-012)

**Status:** Aceita
**Data:** 2026-11-12
**Autores:** time
**Reversibilidade:** alta (telas e dois campos novos numa resposta; sem tabela nem migração)

---

## Contexto

As tasks 12 a 17 deixaram no servidor fatura, limite, gasto real, receita, reserva, sobra do R2 e
alertas. A task 18 mostra isso na tela. O ADR 015 proíbe regra de cálculo no front; o ADR 023
define a tela principal (sem o vale); o ADR 044 diz que não há estado de fatura "paga" e o
ADR 048 (item 9) diz que a fatura está aberta enquanto `hoje` é anterior ao fechamento efetivo.
Faltavam decisões de tela e um dado que a API não expunha.

## Decisão

1. **Aberta ou fechada vem da API.** `GET /api/cartoes/{conta_id}/faturas/{competencia}` ganha
   `fechamento` (data do fechamento efetivo, função SQL `fatura_fechamento`) e `situacao`
   (`aberta` se `fechamento > hoje`, senão `fechada`; nulos sem dia de fechamento cadastrado). A
   comparação é feita na consulta SQL, com `hoje` civil de São Paulo injetado (`hoje_civil`), nunca
   do cliente. Não existe "paga": pagar é transferência e não muda a situação (ADR 044).
2. **O front só exibe.** Nível, cobertura, falta, aporte, sobra, alerta, totais e a ordem dos
   alertas são mostrados como vieram. Sobras do front permitidas, todas de apresentação: trocar
   código por rótulo (`critica` → "Crítica", `detalhe` → ação sugerida), juntar id com nome
   (conta, pessoa, recorrente) e testar flags/contagens que a API manda (`config_pendente`,
   `pendencias_vencimento > 0`, `alerta`, `situacao`). Valor negativo é reconhecido pelo sinal "-"
   do texto só para rotular "crédito de estorno" e explicar limite disponível negativo.
3. **Crédito de estorno** (item de fatura com valor negativo) é rotulado "crédito de estorno" e
   não como parcela.
4. **Nomes por cruzamento de ids**: contas (`/api/contas`), pessoas (`/api/pessoas`) e recorrentes
   (`/api/recorrentes`), porque a API de fatura, R2 e alertas devolve só ids. Nome de terceiro
   aparece na tela do próprio usuário (dado dele, em sessão autenticada); não vai a URL, log nem
   cache.
5. **Mês**: gasto real e receita começam no mês corrente de São Paulo e andam para meses
   anteriores (sem ir ao futuro); a fatura anda nos dois sentidos (há parcelas futuras). O
   parâmetro `mes` segue "AAAA-MM"; 422 vira "mês inválido" e 401 volta ao login.
6. **`config_pendente` é pedido de configuração, não alerta**: aviso neutro com link para
   `/parametros` (tela da task 19; até lá o link cai em "página não encontrada"). O item `CONFIG`
   de `/api/alertas` recebe a etiqueta "pedido de configuração".
7. **Sobra não confiável** (`pendencias_vencimento > 0`) aparece como aviso em destaque no início
   e na tela da sobra. Fatura aberta no R2 (`parcial`) é marcada "fatura aberta (parcial)".
   A sobra mostrada é a do R2 (só fatura própria); o total da fatura fica na tela de cartões.
8. **Início** mostra receita de caixa, gasto real, sobra, reserva e alertas; cada cartão busca o
   seu dado, então a falha de um não derruba os outros. O benefício da receita e o vale não
   aparecem (task 20).
9. **Alertas sem dispensar**: a tela antiga de R4 (`GET /api/r4`) foi trocada por `GET /api/alertas`
   (que já traz o R4 por conta); não há botão de dispensar (ADR 049).
10. **Glossário acessível**: cada termo técnico é um botão (`aria-expanded`) que abre a explicação
    na hora, e cada página lista os termos usados num bloco "O que significam estes termos?",
    com texto derivado do `CONTEXT.md`.
11. **PWA**: nenhuma resposta autenticada é guardada; o service worker segue com lista fechada de
    arquivos estáticos e `/api` vai sempre à rede (ADR 040).

12. **Respostas atrasadas e erros**: só a resposta do pedido mais recente vale (corrida: se o
    usuário troca de mês duas vezes, a resposta velha não toma o lugar da nova), e trocar mês,
    competência ou cartão recria o bloco de dados (`key` do React), então valor do mês antigo
    nunca aparece sob o título do mês novo. Quando uma tela junta várias buscas e uma dá 401 e
    outra 500, o 401 vence (volta ao login). Cobertura em meses usa decimal brasileiro
    (`formatarDecimal`: troca o ponto pela vírgula no texto, sem conta).

## Exceção declarada à regra de mascaramento

A regra geral (`.claude/rules/seguranca.md`) é exibir dado pessoal só mascarado. `pessoa.nome`
(o terceiro cuja compra está no cartão) é exibido **em claro**, e só na sessão autenticada do
próprio dono, porque a finalidade do app exige saber quem comprou o quê. É **proibido** fora dela:
log, URL, cache ou storage do navegador (a PWA não guarda resposta da API), pacote do revisor e
analítico. Opcional, a decidir nas tasks 19/20: mostrar só iniciais em listagens densas.

## Dívidas registradas

- O rótulo "crédito de estorno" depende do sinal "-" no texto do valor, o que é frágil. O ideal
  é a API expor um campo de tipo de item da fatura; fica para a próxima SPEC que tocar a fatura.
- O link "Configurar a reserva" aponta para `/parametros`, que só passa a existir na task 19.

## Alternativas consideradas

- Calcular aberta/fechada no front comparando datas ❌ (regra no front, ADR 015).
- Criar tabela/estado de fatura ❌ (ADR 044: não há estado; sai de uma data).
- Esconder o item de configuração da lista de alertas ❌ (a API já o marca como `configuracao`).

## Consequências

- Contrato OpenAPI e cliente TS regenerados (`fechamento` e `situacao` na fatura).
- Menu lateral com 8 itens. Em tela estreita a barra de baixo fica apertada; o design final decide.
- `/parametros` ainda não existe: o link de configuração leva à página não encontrada até a task 19.

## Como verificar

`tests/backend/test_fatura_situacao_api.py`, `frontend/src/leitura/Leitura.test.tsx`,
`frontend/src/leitura/Glossario.test.tsx`, `tests/e2e/test_leitura.py`.

## Impacto em SI/LGPD

Nenhum dado novo é coletado ou guardado. As telas mostram dado financeiro e nomes de terceiros
só na sessão autenticada do próprio usuário; nada vai a log, URL ou cache. O `user_id` segue
vindo da sessão (INV-13); `fechamento` e `situacao` usam o `user_id` da sessão na consulta SQL.
