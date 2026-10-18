---
domain: postgres-financeiro
topic: migracoes
confidence: null
mcp_validated: null
---

# abako — migrações (ADR 025)

- Ferramenta: **Alembic**, só como runner de versões. Migrações escritas à mão com `op.execute("...SQL...")`. **Sem autogenerate** (não há modelos ORM; as regras vivem no SQL).
- Pasta: `db/migrations/`. Uma migração = uma mudança coesa, com `upgrade()` **e** `downgrade()`.
- Alvo por variável de ambiente (`ABAKO_ENV=tst|prd`); o padrão é **tst**. Migração em **prd** pede confirmação do usuário e backup recente (KB `seguranca-local`, backup-restore).
- Toda tabela nova: `user_id NOT NULL`, índice por `user_id`, `NUMERIC` para valores, datas civis como `date`.
- Tabelas de versão do ledger: `REVOKE UPDATE, DELETE` do papel `app`; testar isso.
- Papéis: `app` (CRUD restrito), `pipeline` (SELECT only), dono do esquema (só migração). Senha de admin fora do `.env` (ADR 018).
- Views/funções: `CREATE OR REPLACE` na migração; teste pgTAP/pytest com fixture.
- Ciclo de teste: aplicar do zero no `tst` vazio → `downgrade` até a base → aplicar de novo.
- Nunca `DROP`/`TRUNCATE` em prd sem aprovação e ADR (rules/seguranca).

> Texto escrito a partir dos ADRs do projeto. Versões e flags de ferramentas externas devem ser conferidas na documentação atual (context7) ao implementar; não foram validadas aqui.
