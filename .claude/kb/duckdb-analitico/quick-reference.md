---
domain: duckdb-analitico
topic: quick-reference
---

# DuckDB analítico — Quick Reference

| Assunto | Regra |
|---|---|
| Conteúdo | Só agregados (6 views do ADR 008), com `user_id` |
| Escrita | Um escritor; arquivo novo + renomear (troca atômica) |
| Leitura | `read_only=True` na API |
| Valores | `DECIMAL`, nunca `DOUBLE` |
| Origem | Postgres via papel `pipeline` (SELECT only) |
| Git | `*.duckdb` ignorado; agentes bloqueados |
| Teste | INV-15: sem linhas de transação; pipeline não escreve no transacional |
