# 008 — Camada analítica fisicamente separada (DuckDB)

**Status:** Aceita
**Data:** 2026-10-16
**Autores:** time
**Reversibilidade:** difícil

---

## Contexto

O usuário tem perfil de engenharia de dados e quer o analítico separado do transacional desde o início.

## Decisão

Camada analítica em **DuckDB**, num **arquivo fisicamente separado** do Postgres transacional (pasta própria, permissões próprias), contendo **apenas agregados**. Fluxo **unidirecional**: transacional → analítico.

- O pipeline lê o Postgres por um **papel somente leitura** e escreve só no arquivo DuckDB.
- O pipeline grava num arquivo novo e o troca pelo atual ao final (troca atômica), porque o DuckDB aceita um único escritor por vez e bloqueia leitores durante a escrita.
- O dashboard e a API abrem o arquivo DuckDB em modo somente leitura.

Views: `saldo_diario`, `gasto_mensal`, `fatura_resumo`, `limite_linha`, `a_receber_por_pessoa`, `cobertura_reserva`.

## Alternativas consideradas

### Opção A — Schemas no mesmo banco ❌ Rejeitada
Não isola.

### Opção B — Cópia do dado bruto ❌ Rejeitada
Duplica dado financeiro.

### Opção C — Segundo Postgres separado ❌ Rejeitada
Mais um contêiner e mais credenciais para um volume pequeno.

### Opção D — DuckDB em arquivo separado, só agregados ✅ Escolhida
Arquivo único, tipo `DECIMAL`, feito para consultas analíticas, sem infraestrutura extra.

## Consequências

### Positivas
- Isolamento de leitura do dashboard.
- Sem segundo contêiner de banco.

### Negativas / Tradeoffs
- O pipeline entra no MVP.
- O DuckDB não tem usuários: o isolamento vem do arquivo separado e da permissão da pasta (substitui "credenciais distintas").
- Escritor único: exige a troca atômica de arquivo.

## Premissas

Volume pequeno; o pipeline roda local.

## Fora de escopo

Streaming/real-time (Kafka), lakehouse.

## Como verificar

INV-15; teste de que o analítico não contém linhas de transação e de que o pipeline não escreve no transacional.

## Impacto em SI/LGPD

Minimização: o analítico guarda só agregados, nunca transações.

## Revisão

Revisar se o volume ou os usos mudarem.

*Revisada em 2026-10-16, antes do primeiro commit: o analítico passou de segundo Postgres para DuckDB.*
