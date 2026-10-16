# 002 — Pacote E keyvault-cloud + skill dual + install vault

**Status:** Aceita  
**Data:** 2026-08-12  
**Autores:** time

---

## Contexto

Projetos-filho que usam cofre cloud (OCI Vault ou Azure Key Vault) não tinham no
canônico: (1) norma/checks de wiring, (2) playbook dual, (3) KBs JIT, (4) install
condicional. Cada time inventava facade/map/SDK — com risco de secret em repo e de
acoplar vault a todo `pipeline_dados`.

Decisões do grill (`keyvault-oci-azure-choice`) fecharam: sem agent vault no canônico;
skill dual; pacote **E** ortogonal a A–D; install por categoria nova.

## Decisão

Vamos tratar secrets cloud como **camada ortogonal** ao perfil DE:

1. **Pacote E** `keyvault-cloud` (`DE-E001`–`E003`) em `data-engineering.yaml` + checks FS
   em `package_e.py`. Engine injeta E quando `secret_store` (marker) ou auto-detect vault
   aplica. `DE-A001` permanece para literais no código.
2. **Skill dual** `cloud-secrets` + KBs `oci-vault` e `azure-keyvault` (espelho
   `.claude`↔`.cursor`) — sem agent canônico dedicado.
3. **Install** via categoria nova `cloud_secrets` no `stack_map` (keywords
   `secret_store|keyvault|azure-keyvault|oci-vault` + inject do marker) — **não**
   acoplada a `pipeline_dados`. Examples `keyvault-*-min` fora do install.
4. Pergunta OCI vs Azure **somente** em grill/define (default por stack + confirmação).

## Alternativas consideradas

### Opção A — Agent `key-oci-expert` no canônico ❌ Rejeitada

Duplicaria a skill/KBs e acoplaria o catálogo a um vendor. Grill: sem agent.

### Opção B — Pacote E + skill dual + install condicional ✅ Escolhida

Norma auditável (`DE-E*`), playbook único dual-cloud, propagação só quando a stack
pede vault. Alinha A–D (kernel) com catálogo JIT.

### Opção C — Sempre instalar vault com `pipeline_dados` ❌ Rejeitada

Projetos DE sem cofre pagariam artefato irrelevante; viola minimização do install.

### Opção D — Duas skills (oci-secrets / azure-secrets) ❌ Rejeitada

Duplicaria SI/wiring; grill fechou skill dual `cloud-secrets`.

## Consequências

### Positivas
- Wiring vault mensurável no `/validar` (FS only, sem live API).
- Install opt-in; examples dogfood fora do `stack_map`.
- SI explícito: nunca logar secret; placeholders em examples.

### Negativas / Tradeoffs
- Heurística de auto-detect pode falso-positivo — mitigada por marker override +
  keywords conservadoras no install.
- Contagens de skills/KBs sobem (21/21); sync de `CLAUDE.md`/`AGENTS.md` obrigatório.

### Riscos
- Confundir E com A001 — documentado: E = wiring; A001 = literais.

## Impacto em SI/LGPD

- Domínio de **credenciais** (nível SI b): sem PII de produto nos artefatos.
- Invariantes: nunca logar valor; map só IDs/URIs; sem secret real no git.
- Ponte em `rules/seguranca` (+ `.mdc`); revisor trata vazamento como bloqueante.

## Revisão

Esta ADR deve ser revisada se:
- Entrar outro cofre (AWS Secrets Manager / HashiCorp) no canônico
- O install precisar de flag explícita além de keywords/marker
- Live API vault passar a ser exigida no CI (hoje fora de escopo)
