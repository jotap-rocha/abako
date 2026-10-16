---
topic: time-travel-versioning
confidence: null
mcp_validated: null
---

# Time Travel e Versionamento

## O modelo: tabela como sequência de snapshots imutáveis

Toda escrita em um open table format cria um **novo snapshot** — nunca sobrescreve o anterior in
place. A "tabela atual" é apenas um ponteiro para o snapshot mais recente. Isso é o que viabiliza
time travel: consultar um snapshot antigo é só resolver o ponteiro para uma versão anterior, sem
precisar reconstruir nada.

| Formato | Onde vive o histórico | Como referenciar versão antiga |
|---|---|---|
| Iceberg | Snapshots (metadata JSON) + manifest lists apontando para manifest files | `VERSION AS OF <snapshot_id>` / `TIMESTAMP AS OF <ts>` |
| Delta Lake | Transaction log `_delta_log/*.json` (um arquivo por commit) + checkpoints | `VERSION AS OF <version>` / `TIMESTAMP AS OF <ts>` |
| Hudi | Timeline (`.hoodie/`) — instants de commit/clean/compaction | `AS OF INSTANT <timestamp>` |

## Casos de uso

- **Auditoria/compliance**: reconstruir exatamente o estado de uma tabela em uma data específica
  (ex.: "como estava esse relatório financeiro em 31/12").
- **Rollback**: erro de pipeline corrompeu a tabela → reverter o ponteiro para o snapshot anterior
  é uma operação de metadados, não uma restauração de backup.
- **Reprodutibilidade de ML**: treinar/re-treinar um modelo contra o snapshot exato usado
  originalmente, mesmo que a tabela tenha evoluído desde então.
- **Debug de pipeline**: comparar snapshot pré e pós-transformação para isolar onde um dado
  divergiu.

## Exemplo (Spark SQL, sintaxe similar entre Iceberg e Delta)

```sql
-- Iceberg
SELECT * FROM catalog.db.orders VERSION AS OF 3821;
SELECT * FROM catalog.db.orders TIMESTAMP AS OF '2026-06-01 00:00:00';

-- Delta Lake
SELECT * FROM db.orders VERSION AS OF 3821;
SELECT * FROM db.orders TIMESTAMP AS OF '2026-06-01';

-- Rollback (Delta)
RESTORE TABLE db.orders TO VERSION AS OF 3821;

-- Rollback (Iceberg)
CALL catalog.system.rollback_to_snapshot('db.orders', 8390223109123456789);
```

## Relação com retenção

Time travel só funciona enquanto o snapshot antigo ainda existe fisicamente. Job de retenção
(`VACUUM` no Delta, `expire_snapshots` no Iceberg) apaga snapshots/arquivos órfãos além de uma
janela configurada — ver `patterns/retention-vacuum.md`. Configurar essa janela é o trade-off
central: mais retenção = mais time travel disponível, mas mais custo de storage e catálogo maior
(mais metadados para escanear).

## Gotchas

- **Time travel não substitui backup/disaster recovery**: se o job de retenção já rodou, a versão
  antiga simplesmente não existe mais fisicamente.
- **Snapshots não são baratos indefinidamente**: catálogos com milhares de snapshots sem limpeza
  degradam performance de planejamento de query (mais manifests/log entries para ler).
- **`TIMESTAMP AS OF` resolve para o snapshot mais próximo ANTES do timestamp**, não o mais
  próximo — atenção em timezone ao comparar com logs de auditoria.
- **Streaming/CDC**: consumir uma tabela via time travel fixo em um pipeline de streaming
  incremental é um anti-padrão — streaming deve seguir o log incremental (`readChangeFeed` no
  Delta, `incremental read` no Hudi/Iceberg), não re-consultar snapshots fixos.
