---
topic: dab-bundle-identity
confidence: null
mcp_validated: null
---

# DAB / Bundle — identidade de execução (DE-D001)

## Âncora normativa

- **Rule ID:** `DE-D001`
- **Categoria:** `dab-layout`
- **Fonte:** `data-engineering.yaml` (pacote **D**) — severidade e `remediation` **só** no YAML.

## O que resolve

Projetos Databricks precisam de artefato de bundle/job **versionado** (`databricks.yml`
ou equivalente) com **owner** ou **run identity** (`run_as` / service principal) auditável
no repositório. Sem isso, o CI filesystem não prova quem executa o job.

## Sinais no filesystem

- Presença de `databricks.yml`, `bundle.yml` / `bundle*.yml`.
- Campos esperados no manifesto: `owner`, `run_as.service_principal_name` (ou equivalente
  documentado no check).
- Arquivo `OWNER` no example reforça ownership humano, mas **não** substitui a identidade
  no bundle.

## Fora de escopo

- Deploy live (`databricks bundle deploy`) — **não** é requisito do gate canônico.
- Tokens, host URLs com secret, ou chamadas à API — proibidos no CI do canônico.

## Remediação (ponte)

Consulte `remediation` de `DE-D001` no YAML. Em resumo operacional: adicione o YAML do
bundle e declare owner / service principal de execução versionado.

## Ver também

- Pattern: [dab-identity.md](../patterns/dab-identity.md)
- Example: `examples/databricks-sdp-min/databricks.yml`
- Skill: `de-conformidade` → `explain DE-D001`
