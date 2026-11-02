# 032 — Backup com restauração testada na v1

**Status:** Aceita
**Data:** 2026-10-19
**Autores:** time
**Reversibilidade:** moderada

---

## Contexto

Backup criptografado sem teste de restauração não é recuperação (ADR 018 só define a criptografia).

## Decisão

- Backup criptografado (age) e **retenção mínima** definida na SPEC-001.
- A restauração é testada num **banco descartável no mesmo contêiner** (além de `prd` e `tst`), nunca sobre `prd`.
- **Só o usuário executa a restauração** (decisão 2026-10-19): o guardrail contra `dropdb`/`DROP` não ganha exceção, e o teste de restauração fica na rotina manual, fora do `check` automático.
- O script de restauração **recusa o alvo `prd`** (teste); o agente só restaura dump de `tst` ou sintético, e restaurar dump de `prd` é ação humana (o agente não abre backup, ADR 019).
- Critérios de aceite na SPEC-001: retenção, local da chave age e local do teste de restauração.
- Se roda no `check` ou na rotina de deploy local: definido na SPEC-001.
- "Direito ao esquecimento" segue fora da v1; o ciclo de vida dos dados cobre exclusão física do banco e expiração de backups.

## Alternativas consideradas

Backup sem teste ❌.

## Como verificar

Teste de restauração com contagem e soma de saldos conferidas (SPEC-001).

## Impacto em SI/LGPD

Backup contém dado financeiro real: chave privada fora do PC; nunca no pacote do revisor.
