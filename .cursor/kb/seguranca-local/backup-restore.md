---
domain: seguranca-local
topic: backup-restore
confidence: null
mcp_validated: null
---

# abako — backup e restauração (ADR 014, 018, 022)

- Backup **antes** de: migração em prd, deploy local, sessão de agente que altere esquema/dados.
- Formato: `pg_dump -Fc` do banco `prd` (contêiner dedicado, porta própria — nunca 5432) → criptografar com **age** (chave pública no PC; **chave privada fora do PC**).
- Backups vão em pasta fora do repositório (`backups/` é ignorada e bloqueada para agentes). Nunca no git, nunca no pacote do revisor.
- `scripts/deploy-local` **recusa sem backup recente** (limite definido na SPEC; sugestão: 24 h).
- Restauração **testada** (ADR 032): restaurar num **banco descartável dedicado** no mesmo contêiner (além de `prd` e `tst`; nunca em `tst`, que a suíte usa, nunca em `prd`), conferir contagens e soma de saldos. O script **recusa o alvo `prd`**. Backup nunca restaurado não conta.
- Retenção mínima, local da chave age e se o teste roda no `check` ou no deploy local: definidos na SPEC-001.
- O agente só restaura dump de `tst` ou sintético; restaurar dump de `prd` é ação humana.
- Quem executa: o **usuário** (os comandos tocam dados reais; agentes não leem backups — ADR 019).
- O agente pode escrever/ajustar o script e documentar o procedimento, não rodá-lo contra prd.

> Texto escrito a partir dos ADRs do projeto. Versões e flags de ferramentas externas devem ser conferidas na documentação atual (context7) ao implementar; não foram validadas aqui.
