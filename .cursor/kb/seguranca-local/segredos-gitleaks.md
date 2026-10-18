---
domain: seguranca-local
topic: segredos-gitleaks
confidence: null
mcp_validated: null
---

# abako — segredos (ADR 018)

- `.env` ignorado pelo git e **bloqueado** para agentes; `.env.example` só com placeholders (`<SENHA>`), versionado.
- Senha de **admin** do banco **não** entra no `.env`. O `.env` guarda só as credenciais de `app`/`pipeline`/`tst`.
- `COMPOSE_PROJECT_NAME`, porta do Postgres (≠ 5432) e caminhos vêm do `.env`.
- **gitleaks** no pre-commit (`.githooks/pre-commit` hoje só tem heurística simples; substituir/complementar por gitleaks — o usuário instala o binário). CI roda gitleaks sem segredos.
- Teste do hook: um segredo falso é barrado.
- Vazou? Trate como incidente: rotacionar **antes** de commitar de novo (rules/seguranca).
- Nada de segredo em issues, PRs, logs ou no pacote do revisor.

> Texto escrito a partir dos ADRs do projeto. Versões e flags de ferramentas externas devem ser conferidas na documentação atual (context7) ao implementar; não foram validadas aqui.
