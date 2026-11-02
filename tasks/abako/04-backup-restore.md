# SPEC-001d: backup e restauração

**Status:** not started  
**Blocked by:** tasks/abako/03-esquema-base.md

## What to build

Backup criptografado (age) e script de restauração para um banco descartável no mesmo contêiner. O script recusa o alvo `prd`. Só o usuário executa a restauração. Define retenção mínima e onde fica a chave age.

## Acceptance criteria

- [ ] SPEC-001-AC-12: o script de restauração recusa o alvo `prd` — tested by: tests/db/test_restore.py::test_recusa_alvo_prd
- [ ] SPEC-001-AC-13: o backup é criptografado e não contém `.env` nem segredo — tested by: tests/db/test_backup.py::test_backup_criptografado
- [ ] SPEC-001-AC-14: restaurar backup sintético no banco descartável reproduz contagem de linhas e soma de saldos — no test automático — executado pelo usuário (ADR 032); waiver humano com evidência da execução

## Notes

O agente não abre backups (ADR 019) e não ganha exceção no guardrail `dropdb`. Retenção e local da chave: definidos aqui.
