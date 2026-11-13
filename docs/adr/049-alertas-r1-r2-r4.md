# 049 — Alertas R1, R2 e R4: convenções da SPEC-011

**Status:** Aceita
**Data:** 2026-11-12
**Autores:** time
**Reversibilidade:** alta (uma função de leitura; sem tabelas nem dados; o downgrade só remove a função)

---

## Contexto

O ADR 023 definiu os alertas da v1 (R1, R2, R4, R5) mas não disse o que vira alerta em cada caso
de borda: qual severidade tem cada nível da reserva, o que fazer com a configuração pendente, com
a sobra do R2 quando há cartão sem vencimento (ADR 048 item 5) e com as vencidas, e como o R4
(ADR 041) chega à API. Decisões do usuário em 2026-11-12. R3, R6 e R7 ficam fora; o R5 (vale) é
da task 20.

## Decisão

1. **Alerta é derivado na hora.** Função `alertas(p_user, p_hoje)` de leitura (`INVOKER`,
   `STABLE`), que só compõe `reserva_situacao` (ADR 047), `r2_situacao` (ADR 048) e
   `r4_divergencias` (ADR 041). **Sem tabela, sem estado, sem botão de dispensar, sem histórico
   de alertas:** o alerta existe enquanto a condição existe. Os cortes (50% e 100% da meta,
   `sobra < 0`, divergência diferente de zero) continuam nas funções de origem; a função nova só
   decide o que vira alerta e com que severidade. Nenhuma regra em Python (ADR 015).
2. **Linha de alerta:** `codigo` (`R1`, `R2`, `R4`, `CONFIG`), `tipo` (`alerta`, `aviso`,
   `configuracao`), `severidade` (`alta`, `media`, `baixa`), `detalhe` (identificador estável do
   caso), `mensagem` literal (sem valor, nome ou id) e os números do caso em colunas próprias,
   que a API devolve como texto. Ordem: severidade (alta, media, baixa), depois `codigo`,
   `detalhe` e conta.
3. **R1 (reserva), por nível** (`config_pendente` falso):

   | nível | tipo | severidade | detalhe |
   |---|---|---|---|
   | `critica` (< 50% da meta) | alerta | alta | `reserva_critica` |
   | `atencao` (50% a < 100%) | aviso | media | `reserva_atencao` |
   | `saudavel` (>= 100%) | nenhum | | |

   Os cortes são os de INV-17, exatos. **Configuração pendente (gasto essencial ausente ou zero)
   não é R1:** vira um item `CONFIG` (`tipo = configuracao`, severidade `baixa`, detalhe
   `reserva_gasto_essencial`) e nenhum R1. Usuário sem conta de reserva e com meta configurada
   tem saldo zero e, portanto, R1 crítico (consequência direta do nível do ADR 047; F-ALERTA-05).
4. **R2 (sobra):** alerta forte (`R2`, `alerta`, `alta`, `sobra_negativa`) **só se `sobra < 0`
   estrito**; sobra exatamente zero não alerta. Se `pendencias_vencimento > 0` (cartão com dívida
   sem vencimento ou fechamento cadastrado, ADR 048 item 5), a sobra é **não confiável**: o campo
   `sobra_nao_confiavel` vem verdadeiro em todo item R2, e, com a sobra >= 0, sai um aviso próprio
   (`R2`, `aviso`, `media`, `sobra_nao_confiavel`) com a sobra e os totais. As **vencidas**
   (ocorrências sem vínculo com data passada, lista à parte e fora da sobra, INV-19) saem como
   aviso `baixa` (`R2`, `vencidas`) com a quantidade; o detalhe fica na lista do R2.
5. **R4 (divergência)** continua sendo o ADR 041 (derivado menos snapshot, tolerância zero, nunca
   corrige). Vira **uma linha por conta vigente** com divergência (`R4`, `aviso`, `media`,
   `divergencia_saldo`): o snapshot divergente **mais recente até hoje** (data, valor do snapshot,
   derivado e divergência) e a `quantidade` de snapshots divergentes da conta. Snapshot com data
   futura não conta; conta excluída não aparece. `snapshot_vigente` já garante uma linha por
   (conta, data), então a ordem por data é determinística. **Cartão = conta de dívida** (o snapshot de fatura
   foi adiado), sem tratamento à parte. Como o ledger nunca se corrige sozinho, a divergência
   continua visível enquanto o snapshot divergente existir; a v1 não tem "reconhecer".
6. **API `GET /api/alertas`:** `user_id` da sessão (INV-13), `hoje` injetável (dependência
   `hoje_civil`, data civil de `America/Sao_Paulo`, nunca do cliente), dinheiro em texto (INV-14),
   leitura em transação `REPEATABLE READ` somente leitura como `GET /api/r2`. Resposta:
   `data_referencia` e `itens` (já ordenados), cada item com os campos comuns e os blocos
   opcionais `reserva`, `r2` ou `r4`. Valores e mensagens não vão a log nem a URL.
7. **Papéis:** a função fixa `SET search_path = public, pg_temp` (defesa em profundidade; as
   leituras anteriores não fixam, mas a medida é compatível) e `abako_app` executa; `abako_pipeline` não. Nenhuma tabela nova, nenhum privilégio
   de escrita.
8. **Endurecimento de entrada, sem relação com os alertas, na mesma entrega:** `versao` de
   `PUT`/`DELETE` de lançamentos e de todo campo de versão ganha teto `<= 2^31 - 1` (acima disso
   o `integer` do banco estourava em 500; agora é 422); `mes` de `GET /api/gasto-real` e
   `GET /api/receita` passa pelo mesmo guard de `recorrentes` (`AB422`, 422 literal) em vez de
   chegar ao banco com NUL, caractere de controle ou texto longo.

## Consequências

- Migração 0012: só a função `alertas(bigint, date)`. O downgrade a remove, sem recusa (não há
  dado que só exista nesta versão).
- A tela de alertas (tasks 18/19) só exibe: ordem, severidade e texto vêm prontos; o front não
  decide limite nem nível (ADR 015). A tela pode ligar `detalhe` a uma ação (cadastrar vencimento,
  informar gasto essencial, vincular ocorrência).
- O R5 (vale) entra na task 20 como mais um ramo da mesma função (nova migração).

## Alternativas consideradas

- Gravar o alerta em tabela, com "visto" e histórico ❌: estado a mais para sincronizar; a regra é
  derivável a cada consulta e o usuário pediu sem dispensa.
- Compor em Python (três chamadas e `if`) ❌: reimplementaria na camada de serviço a decisão de
  severidade que cabe ao banco (ADR 015).
- Uma linha de R4 por snapshot divergente ❌: a lista cresce para sempre (a divergência não se
  corrige); por conta mais a quantidade dá o mesmo aviso sem ruído. O histórico completo continua
  em `GET /api/r4`.
- Tratar configuração pendente como R1 ❌: não há nível a avaliar; é um pedido de cadastro, e
  alarmar a reserva sem meta seria falso.
- Alertar com sobra zero ❌: zero não é déficit (ADR 023: alerta se < 0).
- Esconder a sobra quando o cartão não tem vencimento ❌: some a informação; melhor mostrar e marcar
  como não confiável.

## Fora de escopo

R3 (limite), R5 (vale, task 20), R6 (receber), R7 (categoria); notificação fora da aplicação;
dispensar, adiar ou reconhecer alerta; histórico de alertas; tela (tasks 18/19).

## Como verificar

INV-12, INV-17, INV-18, INV-19, INV-23 e INV-38; fixtures F-ALERTA-01 a F-ALERTA-05;
critérios SPEC-011-AC-1 a AC-12; `tests/db/test_alertas.py`, `test_alertas_propriedades.py`,
`test_alertas_mensagens.py`, `test_migracao_0012.py`, `test_papeis.py`,
`tests/backend/test_alertas.py`.

## Impacto em SI/LGPD

Dado financeiro pessoal (ADR 014), mas sem dado novo: a função só lê o que as funções de origem já
leem e não grava nada. Filtra por `p_user`, que a API recebe da sessão (INV-13); com o `user_id` de
outro usuário devolve vazio ou só os itens do próprio usuário consultado. As mensagens são
literais: nenhum valor, nome de conta, de recorrente ou de pessoa entra nelas, em log, em URL ou
em serviço externo (a conta aparece só como `conta_id`, e o front resolve o nome na tela). O
`EXECUTE` é só do `abako_app`; o pipeline não lê alertas. Finalidade e minimização inalteradas.

**Risco residual aceito:** como nas migrações 0006 a 0011, a função recebe `p_user` por parâmetro e
não há RLS; a v1 é de um único usuário e o isolamento depende de a API passar o `user_id` da
sessão. Revisar se o produto virar multiusuário.
