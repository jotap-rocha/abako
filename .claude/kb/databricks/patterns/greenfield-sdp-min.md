---
topic: greenfield-sdp-min
confidence: null
mcp_validated: null
---

# Pattern: greenfield SDP mínimo (sdp-min style)

## Quando usar

Novo pipeline Databricks declarativo/medallion no canônico ou filho — espelhar
`examples/databricks-sdp-min/` (fora do install automático).

## Layout alvo

```text
project/
├── databricks.yml                 # DE-D001
├── OWNER
├── config/
│   ├── pipeline.yaml              # pacote A (owner, run_id, logging)
│   ├── layers.yaml                # DE-D002
│   └── schema-rescue-policy.yaml  # DE-D004
├── pipelines/
│   └── orders_sdp.py              # sinal SDP
├── uc/
│   ├── grants.yaml                # DE-D005
│   └── lineage.md                 # DE-D005
└── tests/
```

## Passos

1. Crie `databricks.yml` com `owner` / `run_as` (ver pattern dab-identity).
2. Declare camadas em `config/layers.yaml` (bronze → silver → gold).
3. Adicione stub SDP reconhecível pelo detector (sem SDK live).
4. Versionar schema rescue + UC grants/lineage.
5. Valide: `python -m config.canonical_data_check validate <path>`.

Esperado: pacotes A + D; **DE-D003** skip (sem sinal DLT). Preferir **auto-detect**
(sem override de perfil que mascare o detector), como no example canônico.

## Anti-padrões

- Bundle sem identidade (falha DE-D001).
- SDP sem `layers.yaml` (falha DE-D002).
- Credenciais no repo / chamadas live API no CI.

## Ver também

- Concepts: DE-D001, DE-D002, DE-D004, DE-D005
- Example: `examples/databricks-sdp-min/README.md`
