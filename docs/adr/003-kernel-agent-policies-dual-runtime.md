# 003 — Kernel agent-policies dual-runtime (deny/ask + install foundation)

**Status:** Aceita  
**Data:** 2026-08-13  
**Autores:** time

---

## Contexto

O canônico dogfoodava `permissions.deny` parcial só no Claude, sem PreToolUse, sem
paridade Cursor, e o `/install-harness` gerava filhos com `"deny": []`. Soft policy
`seguranca` e `DE-A002` (código DE) não freavam Bash de sessão nos dois IDEs.

## Decisão

Criar um **kernel separado** `agent-policies` (paralelo a git-hygiene / data-engineering):

1. Contrato `agent-policies.yaml` + engine `config/agent_policies/` (load, match, generate, guard)
2. Híbrido deny-hard / ask; bypass `HARNESS_ALLOW_DESTRUCTIVE=1`; fail closed em deny-hard;
   fail open em ask/opt-in
3. Paridade política Claude ↔ Cursor (PreToolUse + `beforeShellExecution`)
4. Install **foundation always-on** (engine + core + hooks dual + seed `.harness/policies` KEEP)
5. Sem agent “policy officer”; sem Edit policies server-side; `DE-A002` ortogonal (cross-link)

## Alternativas consideradas

### Opção A — Só expandir `permissions.deny` no Claude ❌ Rejeitada

Não cobre Cursor nem fail modes / bypass auditável.

### Opção B — Kernel agent-policies dual + foundation ✅ Escolhida

Contrato versionado + generate único evita drift; install corrige `deny: []`.

### Opção C — Unificar com DE-A002 ❌ Rejeitada

Escopos diferentes (sessão Bash vs código versionado).

### Opção D — Categoria opt-in no install ❌ Rejeitada

SI d exige freio default em todo filho.

## Consequências

### Positivas

- Filho nasce com deny ≠ `[]` e hooks Cursor
- Decisão única (matcher) para ambos os IDEs
- Honesty §1.3 documentada junto ao freio

### Negativas / Tradeoffs

- Falso positivo possível → ask + bypass + fail open em opt-in
- Sem garantia server-side (§1.3)

### Riscos

- Drift de hooks se alguém editar deny à mão — mitigate com generate + testes

## Impacto em SI/LGPD

Nível **d** (ops destrutivas). Logs de bypass sem secret/PII. ADR + `seguranca` para
prod/DDL permanecem. Não introduz PII de domínio.

## Revisão

Aceita no ship `policies-anti-destrutivas` (tasks 41–48).
