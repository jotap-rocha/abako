# 006 — Ledger de transações, histórico e snapshot de saldo

**Status:** Aceita
**Data:** 2026-10-16
**Autores:** time
**Reversibilidade:** difícil

---

## Contexto

O saldo era conferido manualmente em planilha. O sistema precisa ser conferível, auditável e permitir saber o saldo de qualquer dia passado.

## Decisão

O sistema é um **ledger** de transações.

- Edição cria nova versão (append-only, SCD2 "por baixo dos panos"); exclusão é lógica.
- **Saldo derivado** = último snapshot + soma das transações válidas posteriores.
- **Snapshot** de saldo (o que o app do banco mostra) é checkpoint de conferência. Divergência é **sinalizada, nunca corrigida automaticamente**.
- Toda tabela tem `user_id`.
- Cartão é conta de **dívida**; **linha de crédito** é entidade separada (o limite pertence à linha; um banco pode ter dois cartões com faturas separadas e limite compartilhado).
- Importação futura deve ser idempotente.

## Alternativas consideradas

### Opção A — Saldo guardado como número ❌ Rejeitada
Sem origem, não conferível.

### Opção B — Update in place ❌ Rejeitada
Perde histórico.

### Opção C — Correção automática de divergência ❌ Rejeitada
Esconde erro.

### Opção D — Ledger versionado + snapshot ✅ Escolhida
Auditável e reconciliável.

## Consequências

### Positivas
- Auditoria, saldo histórico, reconciliação.

### Negativas / Tradeoffs
- Consultas precisam resolver "versão vigente"; edição é mais cara.

### Riscos
- Usuário precisa lançar transações e fazer snapshots periodicamente.

## Fora de escopo

Multiusuário funcional (só `user_id` preparado); múltiplas moedas.

## Como verificar

INV-03, INV-09, INV-13; teste que edita transação e confere histórico + saldo derivado.

## Impacto em SI/LGPD

Dados financeiros pessoais. Isolamento por `user_id` obrigatório (INV-13).

## Revisão

Revisar se surgir necessidade de multiusuário real ou múltiplas moedas.
