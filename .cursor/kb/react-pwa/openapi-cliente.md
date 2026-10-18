---
domain: react-pwa
topic: openapi-cliente
confidence: null
mcp_validated: null
---

# abako — cliente TS do OpenAPI (ADR 015)

- O contrato é o OpenAPI do FastAPI, **versionado** (`openapi.json` commitado). Mudou a API → regenere o arquivo e o cliente na mesma PR.
- Gerador sugerido: `@hey-api/openapi-ts` (confirmar versão e flags na documentação atual; alternativa: `openapi-typescript` + `openapi-fetch`).
- Código gerado fica em `frontend/src/api/gerado/`; **não editar à mão**. Wrappers próprios em `frontend/src/api/`.
- Valores monetários no schema como `string` (padrão decimal), nunca `number`. Se o gerador produzir `number`, ajuste o schema Pydantic (`Decimal` serializado como string).
- CI: gerar o cliente e falhar se houver diff não commitado.
- Autenticação: cookie de sessão (`credentials: "include"`) + cabeçalho do token CSRF.

> Texto escrito a partir dos ADRs do projeto. Versões e flags de ferramentas externas devem ser conferidas na documentação atual (context7) ao implementar; não foram validadas aqui.
