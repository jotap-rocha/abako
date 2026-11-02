# 035 — Endereço local `abako.localhost`

**Status:** Aceita
**Data:** 2026-10-19
**Autores:** time
**Reversibilidade:** fácil

---

## Contexto

O usuário quer acessar o sistema por um nome amigável em vez de `127.0.0.1:porta`. Um domínio público como `abako.com` exigiria DNS e HTTPS e abriria exposição externa, o que o ADR 031 deixou fora da v1.

## Decisão

- Endereço padrão da v1: **`http://abako.localhost:<porta>`** (porta configurável, padrão 8080). O Chrome resolve `*.localhost` para o próprio PC, sem editar o arquivo `hosts`.
- O serviço continua escutando **só em `127.0.0.1`**.
- A lista de `Host` permitidos (INV-34) inclui `abako.localhost`, `localhost` e `127.0.0.1`; CORS e cookies usam essas origens explícitas.
- O FastAPI serve o frontend e a API na mesma origem.
- **Proxy local** (porta 80 e HTTPS local) fica para depois, se o usuário quiser; acesso por celular, rede local ou domínio próprio continua exigindo ADR próprio (ADR 031).

## Alternativas consideradas

### Opção A — `abako.com` ❌ Rejeitada
Domínio público de terceiros; exige exposição externa.

### Opção B — Entrada no arquivo `hosts` ❌ Rejeitada
Desnecessária: `*.localhost` já resolve no Chrome.

### Opção C — `abako.localhost` sem proxy ✅ Escolhida

## Consequências

### Positivas
- Endereço amigável sem componente novo nem exposição de rede.

### Negativas / Tradeoffs
- A porta aparece no endereço até existir proxy.

## Como verificar

INV-34 (Host permitido); teste de que `abako.localhost` é aceito e um host desconhecido é rejeitado (SPEC-002).

## Impacto em SI/LGPD

Nenhum além do ADR 031: escuta só em `127.0.0.1`.

## Revisão

Revisar ao introduzir proxy local ou acesso externo.
