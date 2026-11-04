# Autenticação scram no Postgres do contêiner (volume existente)

Quem executa: **você**. O agente não mexe no volume nem no `prd` (ADR 019). Decisão e motivo:
ADR 039. Para um volume **novo**, nada a fazer: o `docker-compose.yml` já cria o banco com
scram.

## O problema

A imagem oficial do Postgres roda o `initdb` sem `--auth`. Num volume criado antes desta
mudança, o `pg_hba.conf` tem `local` e `127.0.0.1` como `trust`: quem consegue rodar
`docker exec` no contêiner entra como superusuário **sem senha** (inclusive no `prd`), e o
`PGPASSWORD` dos scripts nem chega a ser conferido. Pela porta publicada (host
`127.0.0.1:5433`) a senha já é exigida, porque a conexão chega pelo gateway do Docker e cai na
última linha (`host all all all scram-sha-256`).

## Antes de começar

1. Faça um backup recente do **`prd`** (o padrão do script é o `tst`, então o alvo vai
   explícito; passos completos em `docs/operacao/backup-restore.md`):

   ```powershell
   $env:ABAKO_CONFIRMA_PRD = "sim"
   .venv\Scripts\python.exe -m scripts.backup --alvo prd
   Remove-Item Env:ABAKO_CONFIRMA_PRD
   ```

   Confira que o arquivo gerado é do `prd` (o nome começa com `abako-prd-`) antes de seguir.
   Confirme também que o contêiner está saudável:
   `docker ps --format "{{.Names}} {{.Status}}"`.
2. O nome do contêiner é `<COMPOSE_PROJECT_NAME>-postgres` (o valor está no seu `.env`).
   Abaixo uso `abako-postgres`; troque se o seu for diferente.

## Passo 1: conferir o estado atual (só leitura)

```powershell
docker exec abako-postgres grep -v -E "^#|^$" /var/lib/postgresql/data/pg_hba.conf
```

Esperado antes do ajuste: as linhas `local` e `host ... 127.0.0.1/32` / `::1/128` terminam em
`trust`. Se já terminarem em `scram-sha-256`, pare: não há nada a fazer.

Confira também que todos os papéis têm hash scram (senão a troca os trancaria para fora):

```powershell
docker exec abako-postgres psql -U abako_admin -d postgres --no-password -Atc "SELECT rolname, left(rolpassword, 14) FROM pg_authid WHERE rolcanlogin ORDER BY 1"
```

Todo papel com senha deve mostrar `SCRAM-SHA-256$`, **inclusive o `abako_admin`**, com o qual
você testa no passo 5. Se algum mostrar `md5...` ou ficar vazio, **não continue**: avise o
agente.

## Passo 2: guardar uma cópia do `pg_hba.conf`

```powershell
docker exec -u postgres abako-postgres cp /var/lib/postgresql/data/pg_hba.conf /var/lib/postgresql/data/pg_hba.conf.antes-scram
```

## Passo 3: trocar `trust` por `scram-sha-256`

```powershell
docker exec -u postgres abako-postgres sed -i -E "/^[^#]/ s/trust$/scram-sha-256/" /var/lib/postgresql/data/pg_hba.conf
docker exec abako-postgres grep -v -E "^#|^$" /var/lib/postgresql/data/pg_hba.conf
```

O resultado deve ser igual ao de um volume novo, com as sete linhas terminando em
`scram-sha-256`. Se sobrar alguma linha com `trust` (por exemplo com espaço no fim ou
comentário na mesma linha), **pare e avise o agente**; não reaplique o comando.

## Passo 4: recarregar (sem reiniciar)

```powershell
docker exec -u postgres abako-postgres pg_ctl reload -D /var/lib/postgresql/data
```

## Passo 5: verificar

Sem senha tem de falhar, com a senha de admin tem de entrar. (O segundo bloco, rodado da raiz
do repositório, lê no `.env` só o caminho do arquivo da senha de admin e depois lê a senha
desse arquivo. O `.env` não vira variável do terminal, então não use
`$env:ABAKO_ADMIN_PASSWORD_FILE` direto: ela vem vazia e o teste falha com
`no password supplied`.)

```powershell
docker exec abako-postgres psql -U abako_admin -d postgres --no-password -Atc "select 1"
```

Esperado: `fe_sendauth: no password supplied`.

```powershell
$arq = ((Select-String -Path .env -Pattern '^ABAKO_ADMIN_PASSWORD_FILE=').Line -split '=',2)[1].Split('#')[0].Trim().Trim('"').Trim("'")
$env:PGPASSWORD = (Get-Content -Raw $arq).Trim()
docker exec -e PGPASSWORD abako-postgres psql -h 127.0.0.1 -U abako_admin -d postgres --no-password -Atc "select 1"
Remove-Item Env:PGPASSWORD
```

Esperado: `1`.

Por fim, rode o `check`, que passa pelo mesmo caminho (`docker exec` com senha):

```powershell
.venv\Scripts\python.exe -m scripts.check --com-banco
```

Validado o passo 5, apague a cópia guardada no passo 2 para ela não ir junto em cópias do
volume (guarde-a só se quiser manter o caminho de desfazer):

```powershell
docker exec -u postgres abako-postgres rm /var/lib/postgresql/data/pg_hba.conf.antes-scram
```

## O que muda no dia a dia

- `docker exec -it abako-postgres psql|dropdb -U abako_admin ...` passa a **pedir a senha**
  (digite a de admin). Não há mais entrada sem senha.
- Os scripts (`backup`, `restaurar`, `criar_papeis`, `criar_descartavel`) já mandam a senha e
  seguem iguais.
- O healthcheck do compose (`pg_isready`) não autentica e continua verde.

## Desfazer

```powershell
docker exec -u postgres abako-postgres cp /var/lib/postgresql/data/pg_hba.conf.antes-scram /var/lib/postgresql/data/pg_hba.conf
docker exec -u postgres abako-postgres pg_ctl reload -D /var/lib/postgresql/data
```

Se travar, use o desfazer acima (ele roda como `postgres` no sistema de arquivos e não depende
de senha de banco). Só recrie o volume a partir do backup (`docs/operacao/backup-restore.md`)
se perder, ao mesmo tempo, a cópia do arquivo e a senha de admin; por isso o backup de
"Antes de começar".
