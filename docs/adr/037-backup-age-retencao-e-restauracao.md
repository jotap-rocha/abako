# 037 — Backup com age, retenção 7+4 e restauração no banco descartável

**Status:** Aceita
**Data:** 2026-11-02
**Autores:** time
**Reversibilidade:** moderada

---

## Contexto

O ADR 018 pediu backup criptografado com a chave privada fora do PC, e o ADR 032 pediu
restauração testada num banco descartável, recusa de `prd`, retenção mínima e local da chave,
tudo definido na SPEC-001. A task 04 (SPEC-001d) fecha esses pontos.

## Decisão

- **Ferramenta:** o binário `age` (Windows: `winget install FiloSottile.age`; CI: pacote `age`
  do Ubuntu 24.04).
- **Chaves:** o PC guarda só a **chave pública** (recipient `age1...`), em
  `ABAKO_AGE_RECIPIENT` (ou num arquivo apontado por `ABAKO_AGE_RECIPIENTS_FILE`), no `.env`.
  A **chave privada** é gerada direto num pendrive, com uma segunda cópia offline, e fica fora
  do PC. O backup recusa um valor que contenha chave privada. A restauração recebe o caminho
  da chave privada **só por argumento** (`--identidade`), na hora, nunca pelo `.env`.
- **Pasta:** `ABAKO_BACKUP_DIR` (no PC do usuário, uma pasta própria de backups do abako),
  caminho absoluto e **fora do repositório**: o script recusa pasta dentro do repositório.
- **Como o dump é obtido:** `pg_dump -Fc` roda **dentro do contêiner do projeto**
  (`docker exec`), o que garante a mesma versão do servidor (17.6) sem instalar cliente no
  Windows. O contêiner é `<COMPOSE_PROJECT_NAME>-postgres` ou `ABAKO_PG_CONTAINER` (no CI, o id
  do serviço do job), e precisa publicar o Postgres **só** em `127.0.0.1:5433` (conferido
  com `docker port`; se a porta também aparecer em `0.0.0.0` ou `[::]`, o script recusa).
  Mensagens de erro de `pg_dump`/`pg_restore`/`age` mostram só o código de saída e a 1ª
  linha de erro sem literais. As linhas `CONTEXT:`/`DETAIL:`/`Command was:`, que podem citar
  valores de linhas reais, são descartadas. A senha vai por `PGPASSWORD` no ambiente (`docker exec -e PGPASSWORD`, sem
  valor), então nunca aparece na linha de comando.
- **Sem dump em claro no disco:** `pg_dump | age -r <pública> -o <arquivo>.parcial` por pipe.
  O `.parcial` já sai cifrado e só é renomeado depois do sucesso. A restauração faz
  `age -d | pg_restore` também por pipe.
- **Alvo do backup:** `tst` por padrão. `prd` passa pelo mesmo guarda das migrações
  (`db.alvo.decidir_alvo`): `ABAKO_CONFIRMA_PRD=sim` tem de vir do ambiente real do processo,
  nunca do `.env`.
- **Nome do arquivo:** `abako-<tst|prd>-AAAAMMDD-HHMMSS.dump.age`, com a hora civil de
  `America/Sao_Paulo`. O nome não leva nenhum dado pessoal.
- **Retenção mínima (7 diários + 4 semanais):** fica o backup mais recente de cada um dos 7
  dias mais recentes que têm backup, mais o mais recente de cada uma das 4 semanas ISO mais
  recentes que têm backup e são anteriores à semana do último backup (as duas camadas se
  somam). O resto expira. Os dias e semanas são contados entre os que têm backup, e não no
  calendário, para que um período sem backup não apague tudo. A seleção é uma função pura
  (`db/retencao.py`). A remoção roda depois de cada backup, só sobre arquivos regulares que
  estão diretamente na pasta configurada, só os que seguem o padrão de nome e só do mesmo
  ambiente.
- **Banco descartável:** `restauracao`, com dono `abako_owner_restauracao`, no mesmo contêiner.
  Ele é criado no init de um volume novo (`initdb/02-restauracao.sh`) ou, num volume que já
  existe, por `python -m scripts.criar_descartavel` (passo de admin, idempotente, nunca apaga).
- **Restauração** (`scripts/restaurar.py`): recusa qualquer alvo diferente de `restauracao`
  (incluindo `prd` e `tst`) **antes** de ler o `.env` ou de conectar. Também confere a URL e o
  `current_database()`, exige o banco **vazio** e nunca apaga nada (sem `--clean`, `DROP` ou
  `dropdb`). Usa `pg_restore --no-owner --no-privileges --exit-on-error --single-transaction`
  e, no fim, imprime a contagem de linhas e as somas `NUMERIC` por tabela. A origem é conferida
  com `python -m scripts.resumo_banco`, em sessão somente leitura.
- **Quem executa:** o usuário roda a restauração (ADR 032), e o guardrail de `dropdb` não ganha
  exceção. Para repetir o teste, é o usuário quem recria o descartável. A restauração fica fora
  do `check`; o backup do `tst` sintético entra no `check` (SPEC-001-AC-13).

## Alternativas consideradas

- `pg_dump` do cliente local ❌: exige instalar o cliente 17 no Windows e no CI (o runner traz
  outra versão), e uma versão diferente da do servidor falha.
- Retenção pelo calendário (as últimas N semanas, contando da data de hoje) ❌: depois de um
  período sem backup, apagaria todos os semanais.
- Restaurar com `--clean` ❌: emite `DROP` e reabre o risco que o ADR 032 fechou.
- Chave privada no PC, protegida por senha ❌: o ADR 018 exige que ela fique fora do PC.

## Consequências

- Perder o pendrive **e** a cópia offline torna todos os backups irrecuperáveis. As duas cópias
  precisam ser conferidas periodicamente (a restauração no descartável faz isso).
- O teste de backup falha se o `age` não estiver no PATH: o usuário precisa instalá-lo.
- O descartável acumula o último restore até o usuário recriá-lo.

## Impacto em SI/LGPD

O backup de `prd` contém dado financeiro real. Ele fica cifrado, fora do repositório e com a
chave privada fora do PC. Os agentes não abrem backups (ADR 019); o teste automático usa só
o `tst` sintético e chaves efêmeras. A saída dos scripts mostra apenas nomes de arquivo e
agregados (contagem e soma), nunca valores individuais. A expiração por retenção faz parte
do ciclo de vida dos dados (ADR 032).
