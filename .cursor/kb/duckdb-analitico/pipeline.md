---
domain: duckdb-analitico
topic: pipeline
confidence: null
mcp_validated: null
---

# abako — analítico em DuckDB (ADR 008)

- Fluxo unidirecional: lê Postgres com o papel `pipeline` (**SELECT only**) → escreve **só** o DuckDB (INV-15).
- Só **agregados** (`saldo_diario`, `gasto_mensal`, `fatura_resumo`, `limite_linha`, `a_receber_por_pessoa`, `cobertura_reserva`). Nada de linha de transação, descrição ou estabelecimento. `user_id` preservado.
- Escritor único: gerar `analitico.novo.duckdb`, validar (contagens, somas contra o Postgres), então **renomear** sobre o atual (troca atômica). API/dashboard abrem em `read_only=True`.
- Valores `DECIMAL`, nunca `DOUBLE`.
- Idempotente: rodar duas vezes produz o mesmo resultado.
- Arquivo `.duckdb` ignorado pelo git e bloqueado para agentes (dado real).
- Teste de INV-15: o analítico não contém tabelas/colunas de transação e o pipeline não consegue escrever no Postgres.

> Texto escrito a partir dos ADRs do projeto. Versões e flags de ferramentas externas devem ser conferidas na documentação atual (context7) ao implementar; não foram validadas aqui.
