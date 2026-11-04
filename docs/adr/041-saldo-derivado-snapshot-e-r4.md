# 041 — Saldo derivado, snapshot e R4: convenções da SPEC-003

**Status:** Aceita
**Data:** 2026-11-04
**Autores:** time
**Reversibilidade:** difícil

---

## Contexto

Os ADRs 006 e 026 definem o saldo derivado, o snapshot e o R4, mas deixam omissos alguns
detalhes que o SQL precisa fixar: o que acontece com transação do próprio dia do snapshot, o
que é o "saldo inicial", como corrigir um snapshot digitado errado sem UPDATE e como tratar
datas futuras. As respostas abaixo vêm da leitura dos ADRs, das invariantes e das fixtures
F-SALDO-01 a 03 (a 03 é nova).

## Decisão

- **Snapshot vale para o fim do dia.** O saldo derivado em T é o último snapshot com data ≤ T
  mais as transações vigentes e não excluídas com `data_snapshot < data_transacao ≤ T`.
  Transação do próprio dia do snapshot já está nele. Sem nenhum snapshot, o saldo parte de zero.
- **O primeiro snapshot da conta é o saldo inicial:** âncora, nunca diverge, porque não há nada
  anterior para comparar. Não existe coluna de saldo inicial. Transações com data ≤ ao primeiro
  snapshot ficam fora do derivado e do R4.
- **R4 (INV-23, INV-30):** cada snapshot, exceto o primeiro, é comparado com o derivado a partir
  do snapshot imediatamente anterior até a data dele. **Divergência = derivado − snapshot**,
  tolerância zero, comparação exata em `numeric`. Divergência em um snapshot não contamina o
  seguinte. O R4 só sinaliza; nada é corrigido (ADR 006).
- **Snapshot é append-only.** `snapshot_saldo` não tem UPDATE nem DELETE para `abako_app`. Para
  corrigir um valor digitado errado, registra-se outro snapshot no mesmo dia: vale o último
  registrado (`snapshot_vigente`); o erro fica como auditoria. Não usa a função de troca de
  vigência do ADR 036.
- **Saldo "atual"** é o saldo em hoje (America/Sao_Paulo, calculado no banco). A API recusa
  snapshot e consulta de saldo com **data futura** (422): o snapshot é o que o app do banco
  mostra agora.
- **Todas as contas** têm a mesma mecânica, inclusive benefício e dívida, sem filtro por tipo.
  R4 de fatura e limite são da SPEC-005.
- **Onde vive a regra:** funções `saldo_derivado(user, conta, em)` e `r4_divergencias(user)` e as
  views `snapshot_vigente` e `transacao_vigente` (migração 0004). Recebem o `user_id` da sessão
  como argumento (INV-13); as views usam `security_invoker`.
- **API desta task:** `GET /api/saldos?em=`, `POST /api/contas/{id}/snapshots`, `GET /api/r4` e
  `POST /api/contas` (criar conta: sem ela não há o que mostrar; editar conta fica para depois).
  Dinheiro sempre texto com 2 casas (INV-14); a conta de outro usuário responde 404.

## Alternativas consideradas

- Snapshot versionado como a transação (SCD2): exigiria a função `SECURITY DEFINER` sem ganho,
  porque o snapshot é âncora observada (ADR 026) ❌.
- Coluna de saldo inicial na conta: duplica o primeiro snapshot ❌.
- Unicidade por (conta, dia) no snapshot: obrigaria UPDATE para corrigir erro ❌.
- Tolerância de centavos no R4: esconde erro, contra o ADR 006 ❌.

## Consequências

- Quem quiser o saldo inicial correto precisa informar um snapshot (o primeiro) com a data em
  que quer começar a contar; transações anteriores a ele não contam.
- Editar uma transação antiga muda o derivado dos dias entre os snapshots, não o snapshot; o R4
  mostra a diferença (fixture F-SALDO-03).
- A edição de transação (SPEC-004) ainda precisa da função de troca de vigência do ADR 036.

## Como verificar

`tests/db/test_saldo.py`, `test_r4.py`, `test_retroativa.py`, `test_snapshot_papeis.py` e
`tests/backend/test_saldos_api.py`; fixtures F-SALDO-01, 02 e 03.

## Impacto em SI/LGPD

Dado financeiro real entra a partir daqui. Toda consulta filtra pelo `user_id` da sessão;
`snapshot_saldo` não tem UPDATE/DELETE para a aplicação; nada vai para log.
