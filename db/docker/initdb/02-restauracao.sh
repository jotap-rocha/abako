#!/bin/sh
# Roda só na primeira inicialização do volume. Cria o banco DESCARTÁVEL `restauracao`
# (teste de restauração de backup, ADR 032/037) e o seu dono. Nunca é tst nem prd.
# Volume já existente: use `python -m scripts.criar_descartavel` (passo de admin).
# Sem `exit`: o entrypoint do Postgres pode carregar este arquivo com `source`.
set -eu

if [ -n "${ABAKO_OWNER_RESTAURACAO_PASSWORD:-}" ]; then
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres \
    -v pw_rest="$ABAKO_OWNER_RESTAURACAO_PASSWORD" <<'SQL'
CREATE ROLE abako_owner_restauracao LOGIN PASSWORD :'pw_rest';
CREATE DATABASE restauracao OWNER abako_owner_restauracao;
REVOKE ALL ON DATABASE restauracao FROM PUBLIC;
SQL
else
  echo "ABAKO_OWNER_RESTAURACAO_PASSWORD vazia: banco restauracao não criado (use scripts.criar_descartavel)"
fi
