# SPEC-011: alertas R1, R2 e R4

**Status:** done  
**Blocked by:** tasks/abako/07-saldo-snapshot.md (R4 e saldo derivado), tasks/abako/15-reserva.md (nível da reserva), tasks/abako/16-recorrentes-r2.md (sobra do R2); todas entregues.
**ADR:** docs/adr/049-alertas-r1-r2-r4.md

## What to build

Alertas R1 (reserva), R2 (sobra do horizonte) e R4 (divergência derivado x snapshot), visíveis na
API. O alerta é DERIVADO NA HORA: sem estado, sem dispensa, sem histórico. Migração 0012 (SQL puro):
função de leitura `INVOKER` `alertas(p_user, p_hoje)` que compõe `reserva_situacao`, `r2_situacao` e
`r4_divergencias` e devolve uma linha por alerta (código R1/R2/R4/CONFIG, tipo, severidade, detalhe,
mensagem literal e os números em colunas próprias), ordenada por severidade. Rota
`GET /api/alertas` (sessão, `hoje` civil injetável, dinheiro em texto). R3, R5 (vale, task 20), R6 e
R7 ficam fora. Sem tela (tasks 18/19).

## Acceptance criteria

Fonte: `tests/contracts/criterios.yaml` (SPEC-011-AC-1..12).

- [x] SPEC-011-AC-1: R1 por nível: crítica = alerta forte (alta), atenção = aviso (media), saudável = nada; cortes exatos — tests/backend/test_alertas.py::test_r1
- [x] SPEC-011-AC-2: R2 dispara quando a sobra do horizonte é negativa — tests/backend/test_alertas.py::test_r2
- [x] SPEC-011-AC-3: R4 aparece na API como condição visível, por conta (cartão = conta de dívida) — tests/backend/test_alertas.py::test_r4_visivel
- [x] SPEC-011-AC-4: sobra zero ou positiva não alerta (só < 0 estrito); vencidas são aviso à parte (baixa)
- [x] SPEC-011-AC-5: configuração pendente (gasto essencial ausente ou zero) não é R1: item `CONFIG`
- [x] SPEC-011-AC-6: cartão com dívida sem vencimento torna a sobra não confiável (`sobra_nao_confiavel`)
- [x] SPEC-011-AC-7: vários alertas ordenados por severidade (alta, media, baixa), depois código
- [x] SPEC-011-AC-8: derivado na hora, sem estado (some quando a condição acaba; só GET)
- [x] SPEC-011-AC-9: isolamento por user_id (INV-13); `user_id` e `hoje` do cliente ignorados
- [x] SPEC-011-AC-10: API: 401, data civil de São Paulo, dinheiro em texto, valores e nomes fora do log
- [x] SPEC-011-AC-11: papéis (só o app executa), INVOKER/STABLE, mensagens literais, downgrade da 0012
- [x] SPEC-011-AC-12: `versao` com teto 2^31-1 (422, nunca 500) e `mes` com guard AB422 em gasto-real e receita

## Notes

- Fixtures novas F-ALERTA-01..04 (calculadas à mão) e INV-38.
- **Extras aprovados pelo usuário, na mesma entrega:** teto `le=2**31-1` em todo campo de `versao`
  de `lancamentos` (PUT, DELETE, estorno), `contas` e `linhas-credito`; guard do `mes` de
  `GET /api/gasto-real` e `GET /api/receita` (`mes_valido`, movido para `backend/erros_banco.py` e
  compartilhado com recorrentes).
- **Para o front (tasks 18/19):** `GET /api/alertas` devolve `{data_referencia, itens}`; cada item
  tem `codigo` (R1, R2, R4, CONFIG), `tipo` (alerta, aviso, configuracao), `severidade` (alta, media,
  baixa), `detalhe` (identificador estável: `reserva_critica`, `reserva_atencao`, `sobra_negativa`,
  `sobra_nao_confiavel`, `vencidas`, `divergencia_saldo`, `reserva_gasto_essencial`), `mensagem`
  literal e um bloco `reserva`, `r2` ou `r4` (os outros vêm nulos). Já vem ordenado; o front só
  exibe. R4 traz só `conta_id` (nome vem de `GET /api/contas`). Ações sugeridas por `detalhe`:
  informar gasto essencial, cadastrar vencimento do cartão, vincular ocorrência vencida,
  conferir o snapshot da conta. Sem "dispensar".
