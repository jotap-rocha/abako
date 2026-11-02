# Backup e restauração: passo a passo (ADR 032/037)

Quem roda estes passos é o **usuário**. Os agentes não abrem backups nem rodam a restauração.
Os comandos ficam na raiz do repositório, no PowerShell.

## 0. Uma vez: instalar o age

```powershell
winget install FiloSottile.age
```

Feche e abra o terminal. `age --version` e `age-keygen --version` precisam responder.

## 1. Uma vez: gerar a chave direto no pendrive

Com o pendrive conectado (exemplo: `E:`), gere a chave nele, sem passar pelo disco do PC:

```powershell
age-keygen -o E:\abako-backup-chave.txt
```

O comando mostra `Public key: age1...`. Essa é a chave **pública**. O arquivo no pendrive guarda
a chave **privada** (linha `AGE-SECRET-KEY-...`).

- Faça uma **segunda cópia offline** do arquivo (outro pendrive, ou impressa e guardada).
- Nunca copie o arquivo da chave privada para o PC, para o repositório ou para o `.env`.
- Sem a chave privada, nenhum backup pode ser restaurado. Perder as duas cópias perde tudo.

Os agentes não leem nem usam esse arquivo: `agent-policies.yaml` (`backup-chave-age`) e
`.claude/settings.json` negam o nome `abako-backup-chave`, `E:\abako-backup-chave.txt` e a pasta
`D:\backups`. Se usar outra letra de drive ou outra pasta, ajuste as entradas `Read/Edit/Write`
do `settings.json`.

## 2. Uma vez: configurar o `.env`

Edite o `.env` à mão (ver `.env.example`):

```dotenv
ABAKO_BACKUP_DIR=D:\backups\abako
ABAKO_AGE_RECIPIENT=age1...          # só a PÚBLICA, copiada do passo 1
ABAKO_OWNER_RESTAURACAO_PASSWORD=<senha nova, só letras e números>
ABAKO_DB_RESTAURACAO_URL=postgresql://abako_owner_restauracao:<mesma senha>@127.0.0.1:5433/restauracao
```

A pasta de backup precisa ficar fora do repositório (o script recusa pasta dentro dele).

Restrinja a pasta ao seu usuário do Windows: os arquivos estão cifrados, mas a lista, as datas
e a possibilidade de apagá-los também importam. Por exemplo, numa vez só:

```powershell
New-Item -ItemType Directory -Force D:\backups\abako | Out-Null
icacls D:\backups\abako /inheritance:r /grant:r "${env:USERNAME}:(OI)(CI)F"
```

Confira com `icacls D:\backups\abako`: só o seu usuário deve aparecer.

## 3. Uma vez: criar o banco descartável `restauracao`

É um passo de admin, igual ao `criar_papeis`. O script lê a senha de admin do arquivo de
`ABAKO_ADMIN_PASSWORD_FILE`:

```powershell
.venv\Scripts\python.exe -m scripts.criar_descartavel
```

## 4. Fazer o backup

```powershell
.venv\Scripts\python.exe -m scripts.backup              # tst (padrão)
$env:ABAKO_CONFIRMA_PRD = "sim"; .venv\Scripts\python.exe -m scripts.backup --alvo prd; Remove-Item Env:ABAKO_CONFIRMA_PRD
```

O script imprime o nome do arquivo gerado (`abako-<amb>-AAAAMMDD-HHMMSS.dump.age`) e os que
expiraram pela retenção. A retenção mantém o backup mais recente de cada um dos 7 dias mais
recentes e o mais recente de cada uma das 4 semanas anteriores; ela só apaga arquivos com esse
padrão de nome, do mesmo ambiente, nessa pasta. Com backups diários, a semana anterior já
está coberta pelos 7 diários, então o alcance efetivo da camada semanal é de **cerca de 4
semanas para trás**. Para guardar backups mais antigos (ex.: mensais), copie-os para outra
pasta, que a retenção não toca. A confirmação de `prd` vale só para esse
comando; nunca a coloque no `.env`.

## 5. Conferir a origem

```powershell
.venv\Scripts\python.exe -m scripts.resumo_banco        # tst; para prd, use --alvo prd com ABAKO_CONFIRMA_PRD=sim
```

Guarde a saída: uma linha por tabela, com a contagem de linhas e a soma das colunas de valor.

## 6. Restaurar no descartável (com o pendrive conectado)

O banco `restauracao` precisa estar **vazio**. Na primeira vez ele já está. Para repetir o
teste, recrie o banco você mesmo (o script nunca apaga nada, e os agentes não podem rodar
`dropdb`). O nome do contêiner é `<COMPOSE_PROJECT_NAME>-postgres`, com o valor de
`COMPOSE_PROJECT_NAME` do seu `.env`. Para conferir, rode `docker ps --format "{{.Names}}"` e
use o nome que termina em `-postgres` (ou o de `ABAKO_PG_CONTAINER`, se você o definiu):

```powershell
docker exec -it <COMPOSE_PROJECT_NAME>-postgres dropdb -U abako_admin restauracao   # só o descartável!
.venv\Scripts\python.exe -m scripts.criar_descartavel
```

Depois restaure:

```powershell
.venv\Scripts\python.exe -m scripts.restaurar --arquivo D:\backups\abako\abako-tst-AAAAMMDD-HHMMSS.dump.age --identidade E:\abako-backup-chave.txt
```

Troque `abako-tst-AAAAMMDD-HHMMSS.dump.age` pelo nome real que o passo 4 imprimiu (ou veja
com `Get-ChildItem D:\backups\abako`); com o texto de exemplo, o script recusa o arquivo.

O script recusa qualquer alvo que não seja `restauracao` (incluindo `prd` e `tst`) antes de
conectar. A decifragem vai direto para o `pg_restore`, sem arquivo em claro no disco.

## 7. Conferir e registrar (SPEC-001-AC-14)

Compare a saída do passo 6 com a do passo 5: a contagem e as somas de cada tabela têm de ser
idênticas. Depois preencha o `waiver` do `SPEC-001-AC-14` em `tests/contracts/criterios.yaml`
com a data, os comandos e a indicação de que as saídas conferiram. Registre só as contagens e
as somas de um backup **sintético** do `tst`, nunca dados de `prd`. Desconecte o pendrive.

**Se você restaurou um backup de `prd`**, o banco `restauracao` passa a conter **dado
financeiro real** e fica no contêiner até ser recriado. Assim que terminar a conferência,
recrie-o vazio com os dois comandos do passo 6 (remover o descartável e rodar
`scripts.criar_descartavel`). Esse passo é seu; nenhum agente o executa.
