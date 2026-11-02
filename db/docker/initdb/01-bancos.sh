#!/bin/sh
# Roda só na primeira inicialização do volume. Cria os bancos `tst` e `prd` (prd vazio)
# e um dono por banco. Papéis app/pipeline e esquema vêm nas migrações (task 03).
set -eu

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres \
  -v pw_tst="$ABAKO_OWNER_TST_PASSWORD" -v pw_prd="$ABAKO_OWNER_PRD_PASSWORD" <<'SQL'
CREATE ROLE abako_owner_tst LOGIN PASSWORD :'pw_tst';
CREATE ROLE abako_owner_prd LOGIN PASSWORD :'pw_prd';
CREATE DATABASE tst OWNER abako_owner_tst;
CREATE DATABASE prd OWNER abako_owner_prd;
REVOKE ALL ON DATABASE tst FROM PUBLIC;
REVOKE ALL ON DATABASE prd FROM PUBLIC;
SQL
