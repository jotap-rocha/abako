# SPEC-001d: backup e restauração

**Status:** done  
**Blocked by:** tasks/abako/03-esquema-base.md

## What to build

Backup criptografado (age) e script de restauração para um banco descartável no mesmo contêiner. O script recusa o alvo `prd`. Só o usuário executa a restauração. Define retenção mínima e onde fica a chave age.

## Acceptance criteria

- [x] SPEC-001-AC-12: o script de restauração recusa o alvo `prd` — tested by: tests/db/test_restore.py::test_recusa_alvo_prd
- [x] SPEC-001-AC-13: o backup é criptografado e não contém `.env` nem segredo — tested by: tests/db/test_backup.py::test_backup_criptografado
- [x] SPEC-001-AC-14: restaurar backup sintético no banco descartável reproduz contagem de linhas e soma de saldos — no test automático — executado pelo usuário (ADR 032); waiver humano com evidência da execução (executado em 2026-11-02, ver tests/contracts/criterios.yaml)

## Notes

O agente não abre backups (ADR 019) e não ganha exceção no guardrail `dropdb`. Retenção e local da chave: definidos aqui.

Retenção: o backup mais recente de cada um dos 7 dias mais recentes + o mais recente de cada uma das 4 semanas anteriores (ADR 037). Chave age: privada só no pendrive (com cópia offline); no PC só a pública em `ABAKO_AGE_RECIPIENT`.

`scripts.criar_descartavel` (passo de admin) é exercitado no CI duas vezes (criação e idempotência); o estado que ele deixa é conferido por `tests/db/test_descartavel.py`. Os guardrails de backup/restauração/prd estão em `tests/test_agent_policies_backup.py`.
