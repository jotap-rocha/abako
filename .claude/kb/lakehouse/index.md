---
domain: lakehouse
description: Open table formats e catálogos de metadados para lakehouse — Iceberg, Delta Lake, Hudi, comparativo agnóstico de vendor
mcp_validated: null
confidence: null
---

# KB: Lakehouse — Open Table Formats

Base de conhecimento comparativa sobre formatos de tabela abertos (Iceberg, Delta Lake, Hudi) e
catálogos de metadados (Unity Catalog, Iceberg REST Catalog, Glue). Escopo deliberadamente
agnóstico de vendor — este harness não é comprometido com nenhuma cloud específica; a escolha de
formato/catálogo é sempre função do workload e do ecossistema já em uso, não de preferência.

## Capability map

| Pergunta | Onde achar a resposta |
|---|---|
| Qual formato de tabela escolher (Iceberg/Delta/Hudi)? | [concepts/open-table-formats.md](concepts/open-table-formats.md) |
| Qual catálogo usar (Unity Catalog/REST/Glue)? | [concepts/metadata-catalogs.md](concepts/metadata-catalogs.md) |
| Como mudar schema sem quebrar consumidores? | [concepts/schema-evolution.md](concepts/schema-evolution.md) |
| Como consultar/reverter uma versão antiga da tabela? | [concepts/time-travel-versioning.md](concepts/time-travel-versioning.md) |
| Como mudar o particionamento sem reescrever a tabela? | [patterns/partition-evolution.md](patterns/partition-evolution.md) |
| Muitos arquivos pequenos degradando leitura? | [patterns/compaction-small-files.md](patterns/compaction-small-files.md) |
| Como migrar tabela Hive legada para formato aberto? | [patterns/hive-to-open-format-migration.md](patterns/hive-to-open-format-migration.md) |
| Como limpar snapshots/arquivos antigos com segurança? | [patterns/retention-vacuum.md](patterns/retention-vacuum.md) |

## Conceitos

| Arquivo | Tópico |
|---|---|
| [open-table-formats.md](concepts/open-table-formats.md) | Iceberg vs Delta Lake vs Hudi — o que resolve e comparação |
| [metadata-catalogs.md](concepts/metadata-catalogs.md) | Unity Catalog vs Iceberg REST Catalog vs Glue Data Catalog |
| [schema-evolution.md](concepts/schema-evolution.md) | Evolução de schema em tabelas versionadas (field IDs, column mapping) |
| [time-travel-versioning.md](concepts/time-travel-versioning.md) | Modelo de snapshots, time travel, rollback |

## Padrões

| Arquivo | Tópico |
|---|---|
| [partition-evolution.md](patterns/partition-evolution.md) | Particionamento evolutivo (partition evolution do Iceberg) |
| [compaction-small-files.md](patterns/compaction-small-files.md) | Compaction/otimização de arquivos pequenos |
| [hive-to-open-format-migration.md](patterns/hive-to-open-format-migration.md) | Migração de tabela Hive tradicional para formato aberto |
| [retention-vacuum.md](patterns/retention-vacuum.md) | Retenção/vacuum de versões antigas |

## Conformidade DE (ponte)

Fonte: `data-engineering.yaml` — este KB **não** duplica severidade nem texto normativo.

| Âncora | Relação |
|---|---|
| `DE-A*` | Universal |
| pacote **D** (`DE-D*`) | lakehouse / Databricks cloud (FS checks) |

## Learning path

1. Comece por `concepts/open-table-formats.md` para entender o que um open table format resolve.
2. Leia `concepts/metadata-catalogs.md` — a escolha de catálogo geralmente pesa mais que a de formato.
3. Para operar uma tabela em produção, `concepts/schema-evolution.md` e
   `concepts/time-travel-versioning.md` cobrem os mecanismos de mudança segura.
4. Os 4 arquivos de `patterns/` são receitas operacionais — leia sob demanda, não em sequência.

## Quick Reference

Ver [quick-reference.md](quick-reference.md) — tabela comparativa condensada e comandos por
formato. Ler só se a tarefa exigir esse nível de detalhe.

## Nota de validação

Este domínio foi criado sem acesso ao Context-7 MCP nesta sessão (servidor configurado em
`.mcp.json`, mas indisponível/sem conexão no momento da criação — `claude mcp list` reportou
"Failed to connect"). `mcp_validated` e `confidence` estão como `null` — mesma convenção já usada
no domínio `rag` deste repositório. Rode uma auditoria (Modo 2 do `kb-architect`) assim que o
Context-7 estiver acessível para validar/atualizar este domínio com confidence real.
