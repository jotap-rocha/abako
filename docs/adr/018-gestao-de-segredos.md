# 018 — Gestão de segredos com `.env` e gitleaks

**Status:** Aceita
**Data:** 2026-10-16
**Autores:** time
**Reversibilidade:** difícil

---

## Contexto

Não há cofre em nuvem disponível; o usuário escolheu `.env`.

## Decisão

- `.env` **fora do git** + `.env.example`.
- **gitleaks** no pre-commit.
- Backup **criptografado** (age sugerido; chave privada fora do PC).
- A **senha de admin do banco NÃO fica no `.env`**.

## Alternativas consideradas

### Opção A — Vault/cloud ❌ Rejeitada
Sem acesso.

### Opção B — `.env` + gitleaks ✅ Escolhida

## Consequências

### Positivas
- Simples.

### Negativas / Tradeoffs
- Depende da disciplina do hook.

## Premissas

O usuário mantém a chave de backup fora do PC.

## Fora de escopo

Rotação automática; cofre.

## Como verificar

Teste do hook gitleaks (segredo falso é barrado); `.env` no `.gitignore`; busca por senha de admin no `.env.example`.

## Impacto em SI/LGPD

Ver `rules/seguranca.md`: nunca logar secret; placeholders only em artefatos versionados.

## Revisão

Revisar se um cofre ficar disponível.
