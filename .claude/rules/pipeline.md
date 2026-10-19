---
# Regras do pipeline transacional → analítico (Postgres → DuckDB) do abako
paths:
  - "pipeline/**"
---

# Pipeline (Postgres → DuckDB)

O pipeline alimenta a camada analítica (ADR 008). Fluxo **unidirecional**: lê o transacional, escreve só o analítico (INV-15).

- **Leitura:** pelo papel `pipeline`, **somente leitura**, no Postgres. Nunca escreva no transacional.
- **Escrita:** só no arquivo DuckDB. Grave num **arquivo novo** e troque pelo atual ao final (troca atômica): o DuckDB tem escritor único e bloqueia leitores durante a escrita.
- **Só agregados.** Nenhuma linha de transação, descrição ou estabelecimento no analítico. Views: `saldo_diario`, `gasto_mensal`, `fatura_resumo`, `limite_linha`, `a_receber_por_pessoa`, `cobertura_reserva`.
- **Dinheiro:** `DECIMAL`/`Decimal`, nunca float (INV-14).
- **Idempotente:** reexecutar sobre os mesmos dados produz o mesmo arquivo analítico.
- **Execução única:** `pg_advisory_lock` impede duas execuções simultâneas do pipeline (ADR 029, SPEC-014).
- **`user_id` preservado** nos agregados (INV-13).
- **Config via settings/`.env`;** nenhum caminho, host ou senha hardcoded.
- **Logs:** por etapa (`etapa`, `run_id`, `registros_lidos`, `registros_escritos`, `duracao_ms`), sem dado pessoal nem valores.
- **Teste:** com fixtures e contra o `tst`; o teste de INV-15 prova que o analítico não contém transações e que o pipeline não escreve no transacional.
- **O arquivo `.duckdb` nunca vai para o git.**
