---
domain: duckdb-analitico
description: DuckDB como camada analítica do abako — arquivo único, escritor único, agregados, troca atômica e leitura somente leitura
mcp_validated: null
confidence: null
---

# KB: DuckDB analítico

Decisão no ADR 008. Usado pelo `fin-pipeline`.

## Tópicos
- Arquivo `.duckdb` separado do Postgres; sem usuários — isolamento por arquivo e permissão de pasta.
- Escritor único: gerar arquivo novo, validar, renomear sobre o atual.
- Leitura pela API/dashboard com `read_only=True`.
- Tipos: `DECIMAL(p,s)`, nunca `DOUBLE`, para valores monetários.
- Ler o Postgres: extensão `postgres` do DuckDB (ATTACH somente leitura) ou driver Python com o papel `pipeline`.
- Idempotência: reexecutar gera o mesmo conteúdo.

## Fronteiras
- Regras financeiras ficam no Postgres (`postgres-financeiro`); o analítico só agrega.

## Nota de validação
Criado sem Context-7 (`mcp_validated`/`confidence` = `null`). Confirmar sintaxe de ATTACH e versões ao implementar a SPEC-014.
