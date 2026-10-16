# 014 — Plataforma local-first, bancos prd e tst

**Status:** Aceita (risco assumido pelo usuário)
**Data:** 2026-10-16
**Autores:** time
**Reversibilidade:** difícil

---

## Contexto

O usuário quer aproveitar os recursos da própria máquina (Windows 11 Home) e usar um celular Android antigo.

## Decisão

- Tudo **local (on premise)**, `localhost` apenas.
- **Dois bancos Postgres: `prd` e `tst`**, num **contêiner Postgres dedicado ao projeto**, separado do Postgres que o usuário já usa em outro projeto. O analítico é um arquivo DuckDB (ADR 008).
- **Docker Desktop** (já em uso pelo usuário).
- O nome do projeto é provisório: nomes de contêiner, volume e rede vêm de uma variável (`COMPOSE_PROJECT_NAME` no `.env`), nunca fixos no código, para a renomeação ser trivial.
- **Backup antes** de sessões de agente que alterem esquema ou dados; operações destrutivas pedem confirmação.
- **Sem ambiente apartado nem dados sintéticos para desenvolvimento:** o usuário assume o risco de desenvolver com os dados reais.
- Criptografia de disco ignorada por decisão do usuário.

## Alternativas consideradas

### Opção A — Nuvem ❌ Rejeitada
Sem necessidade nem acesso agora.

### Opção B — Ambiente sintético separado ❌ Rejeitada pelo usuário

### Opção C — Reaproveitar o Postgres do outro projeto ❌ Rejeitada
Mistura dados e credenciais de projetos diferentes; um erro de agente ou migração poderia afetar o outro.

### Opção D — Local-first com `prd` e `tst` em contêiner dedicado ✅ Escolhida

## Consequências

### Positivas
- Custo zero.

### Negativas / Tradeoffs
- Risco maior de um agente tocar dado real (mitigado pelo ADR 019 e por backup).

### Riscos
- Windows Home sem BitLocker completo; acesso só pela máquina/rede local.

## Fora de escopo

Hospedagem; acesso externo; mobile fora da rede local.

## Como verificar

Serviços escutam só em `127.0.0.1`; a suíte de testes aborta se a conexão não for `tst`.

## Impacto em SI/LGPD

Dados financeiros reais em desenvolvimento. `prd` é somente leitura para agentes (`rules/seguranca.md`).

## Revisão

Revisar se o sistema sair da máquina local ou ganhar outros usuários.
