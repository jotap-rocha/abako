# 036 — Papéis do banco criados fora da migração e fechamento de versão

**Status:** Aceita
**Data:** 2026-11-01
**Autores:** time
**Reversibilidade:** média

---

## Contexto

A task 03 exige `app` sem UPDATE/DELETE nas tabelas de versão e `pipeline` só leitura. Três
fatos colidem: papéis (`CREATE ROLE`) são do cluster e compartilhados por `tst` e `prd`; o dono
de cada banco não tem CREATEROLE; senhas não podem estar no código nem no git (ADR 018). Além
disso, a unicidade parcial da versão vigente (INV-27) exige marcar a versão antiga como não
vigente, o que seria um UPDATE.

## Decisão

- **Criação dos papéis** `abako_app` e `abako_pipeline` por passo de admin
  (`python -m scripts.criar_papeis`): senhas de `ABAKO_APP_PASSWORD`/`ABAKO_PIPELINE_PASSWORD`
  (`.env`), senha de admin do arquivo `ABAKO_ADMIN_PASSWORD_FILE` (fora do repo). Idempotente.
  `pipeline` recebe `default_transaction_read_only = on`.
- **A migração só concede privilégios** (GRANT por banco) e falha com mensagem clara se os
  papéis não existem. O downgrade revoga o que concedeu e **não** derruba os papéis (são
  compartilhados com `prd`).
- `app`: `SELECT, INSERT` nas tabelas de versão e em `usuario`; `USAGE` nas sequências de id
  lógico. `pipeline`: `SELECT`.
- **Esquema**: `usuario` (`user_id`), `conta_versao` (com `conta_beneficio`) e
  `transacao_versao`; colunas `conta_id`/`transacao_id` (identidade lógica), `versao`
  (controle otimista), `vigente`, `excluida` (exclusão lógica). Índice único parcial
  `(user_id, id_logico) WHERE vigente`. Chave de idempotência `UNIQUE (user_id, chave)` gravada
  só na versão criadora (NULLs não colidem).
- **Pendência decidida para a SPEC-003/004**: como `app` não tem UPDATE, a troca de vigência
  (antiga vira não vigente, nova entra vigente) será feita por função `SECURITY DEFINER` do dono,
  numa única transação, com `EXECUTE` concedido a `app`. Não é criada agora (sem regra de
  negócio na task 03).

## Alternativas consideradas

- Criar os papéis na migração: exige CREATEROLE/superuser para o dono ou senha de admin no fluxo
  do Alembic ❌.
- `GRANT UPDATE (vigente)` em nível de coluna a `app` ❌: reabre UPDATE na tabela de versão.
- Vigência derivada (maior `versao`) sem flag ❌: não permite índice único parcial (INV-27).

## Impacto em SI/LGPD

Reduz superfície: a aplicação não altera nem apaga histórico. Nenhuma senha em código ou git;
o script nunca imprime segredos. Papéis são do cluster: `prd` herda as mesmas credenciais, e
as grants em `prd` só ocorrem quando o usuário rodar a migração lá (ADR 019).
