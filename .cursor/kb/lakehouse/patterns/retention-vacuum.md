---
topic: retention-vacuum
confidence: null
mcp_validated: null
---

# Estratégia de Retenção / Vacuum de Versões Antigas

## Por que acumula

Cada escrita cria um novo snapshot; operações de compaction e schema evolution também geram
arquivos de dados/metadados novos sem apagar os antigos automaticamente. Sem um job de retenção
rodando periodicamente, o storage cresce indefinidamente com:

- **Arquivos de dados órfãos**: substituídos por compaction/overwrite, mas ainda referenciados por
  snapshots antigos (por isso não podem ser apagados sem antes expirar o snapshot que os referencia).
- **Metadados de snapshot**: manifest lists/manifest files (Iceberg) ou entradas de log
  (`_delta_log/*.json`, Delta) que acumulam mesmo depois que os dados não têm mais uso.

## O trade-off central

Mais retenção = mais janela de time travel (`concepts/time-travel-versioning.md`) e mais margem
para leitores concorrentes de longa duração terminarem antes que os arquivos que estão lendo
sejam apagados. Menos retenção = menos custo de storage e catálogo mais enxuto (queries mais
rápidas de planejar). Não existe valor "certo" — é uma decisão de produto/compliance.

## Iceberg

```sql
-- Expira snapshots mais antigos que N dias, mantendo pelo menos os últimos K
CALL catalog.system.expire_snapshots(
    table => 'db.orders',
    older_than => TIMESTAMP '2026-06-26 00:00:00',
    retain_last => 5
);

-- Remove arquivos de dados órfãos (não referenciados por nenhum snapshot vivo)
-- Rodar DEPOIS de expire_snapshots, nunca antes
CALL catalog.system.remove_orphan_files(
    table => 'db.orders',
    older_than => TIMESTAMP '2026-06-19 00:00:00'
);
```

## Delta Lake

```sql
-- Remove arquivos de dados não referenciados pela versão atual há mais de N horas
VACUUM db.orders RETAIN 168 HOURS;  -- 7 dias, mínimo recomendado por padrão

-- Rodar sem apagar de fato, só listar o que seria removido:
VACUUM db.orders RETAIN 168 HOURS DRY RUN;
```

`VACUUM` com retenção abaixo do padrão (< 7 dias) exige desabilitar explicitamente uma proteção de
segurança (`spark.databricks.delta.retentionDurationCheck.enabled=false`) — sinal de que é uma
operação que o formato trata como potencialmente perigosa por padrão.

## Hudi

O **cleaner service** roda por política configurável (`KEEP_LATEST_COMMITS`,
`KEEP_LATEST_FILE_VERSIONS`) e pode rodar inline ou como job async, análogo ao clustering.

## Regras de segurança

1. **Nunca definir retenção menor que a maior transação em andamento concorrente** — se um job
   pode ler por 6h, retenção mínima precisa ser maior que isso, senão o job falha lendo arquivo
   apagado no meio da execução.
2. **Ordem importa (Iceberg)**: sempre `expire_snapshots` antes de `remove_orphan_files` — remover
   arquivos órfãos antes de expirar snapshots que ainda os referenciam corrompe o snapshot.
3. **Retenção e compliance andam juntas**: se há requisito regulatório de auditoria (ex.: reter
   histórico auditável por X anos), a política de vacuum precisa refletir esse requisito — não é
   só uma decisão de custo de storage.
4. **Agendar, não rodar manual**: vacuum/expire_snapshots deve ser um job recorrente (diário/semanal),
   coordenado com o job de compaction — compaction gera arquivos novos que tornam os antigos órfãos,
   e vacuum é quem efetivamente libera o espaço.

## Gotchas

- **`DRY RUN` primeiro em tabelas de produção** — sempre validar o que seria apagado antes de
  rodar de fato, especialmente após mudar a janela de retenção.
- **Retenção curta quebra time travel silenciosamente**: uma query `TIMESTAMP AS OF` para uma data
  fora da janela de retenção falha ou retorna erro — não é um erro óbvio de configuração até
  alguém tentar auditar dados antigos.
- **Vacuum não é reversível**: arquivos removidos não voltam — é uma das poucas operações
  genuinamente destrutivas neste domínio; tratar com a mesma cautela de DDL destrutivo em produção.
