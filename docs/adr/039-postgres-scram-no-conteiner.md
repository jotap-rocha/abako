# 039 — Autenticação scram dentro do contêiner do Postgres

**Status:** Aceita
**Data:** 2026-11-03
**Autores:** time
**Reversibilidade:** fácil

---

## Contexto

Achado do `fin-seguranca` na task 04 (severidade média). A imagem oficial do Postgres roda o
`initdb` sem `--auth`, o que deixa `local` (socket) e `host 127.0.0.1/32` / `::1/128` como
`trust`. Quem consegue rodar `docker exec` no contêiner vira superusuário em `tst` e `prd` sem
senha, e o `PGPASSWORD` que os scripts de backup mandam nem é conferido. A porta publicada em
`127.0.0.1:5433` já exige senha (a conexão chega pelo gateway do Docker e cai em
`host all all all scram-sha-256`), então o buraco é o acesso por dentro do contêiner.

## Decisão

- `POSTGRES_INITDB_ARGS="--auth-local=scram-sha-256 --auth-host=scram-sha-256"` no
  `docker-compose.yml` (volumes novos) e no serviço Postgres do CI, para o CI testar a mesma
  configuração. Verificado num contêiner descartável: o init dos bancos roda normalmente, o
  `pg_hba.conf` sai todo em scram, sem senha é recusado, senha errada é recusada.
- Volume **existente** (tem o `prd`): o ajuste do `pg_hba.conf` é manual e do **usuário**
  (`docs/operacao/postgres-scram.md`), com cópia do arquivo, recarga sem reinício e desfazer.
  O agente não toca no volume (ADR 019).
- Os comandos de `db/conteiner.py` não mudam: já usam `-h 127.0.0.1`, `PGPASSWORD` e
  `--no-password`. O que muda é o uso interativo (`docker exec ... dropdb -U abako_admin`), que
  passa a pedir a senha de admin.

## Alternativas consideradas

- `POSTGRES_HOST_AUTH_METHOD=scram-sha-256`: só afeta a linha `host all all all`, que já é
  scram; não corrige `local` nem `127.0.0.1` ❌.
- Montar um `pg_hba.conf` próprio no compose: some a vantagem do `initdb` padrão e a diferença
  entre volume novo e antigo continua ❌.
- Recriar o volume do `prd` a partir de backup: resolve, mas é destrutivo e desnecessário para
  trocar uma linha de configuração ❌.

## Consequências

- Quem tem `docker exec` ainda consegue ler os arquivos do contêiner, mas deixa de ser
  superusuário do banco sem a senha de admin.
- Se algum papel tivesse senha em formato antigo (`md5`), a troca o trancaria para fora; o
  passo 1 do runbook confere isso antes.
- Não protege contra quem lê o arquivo da senha de admin ou tem a conta do Windows (ADR 031).

## Como verificar

`tests/test_compose_scram.py` (compose e CI trazem os argumentos); `check --com-banco` e o CI
passam pelo `docker exec` com scram; no volume existente, o passo 5 do runbook.

## Impacto em SI/LGPD

Reduz a superfície de acesso a dado financeiro real no `prd`. Nenhum dado novo.
