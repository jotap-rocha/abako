# 010 — Entrada de dados manual na v1

**Status:** Aceita
**Data:** 2026-10-16
**Autores:** time
**Reversibilidade:** fácil

---

## Contexto

Open Finance e integração automática têm custo e regras próprias; os extratos chegam em PDF/e-mail.

## Decisão

**Lançamento manual** na v1, com autocomplete. Adaptadores de importação e tabela de staging ficam para depois, mas o modelo já aceita idempotência (INV-16).

## Alternativas consideradas

### Opção A — Scraping de bancos ❌ Rejeitada
Risco e fragilidade.

### Opção B — Open Finance agora ❌ Rejeitada
Complexidade e regulação.

### Opção C — Lançamento manual ✅ Escolhida

## Consequências

### Positivas
- Zero credenciais bancárias; máximo controle.

### Negativas / Tradeoffs
- Fricção de lançar.

## Premissas

O usuário segue lançando; extratos só entram depois.

## Fora de escopo

Leitura de PDF; canal de e-mail/WhatsApp; Open Finance.

## Como verificar

Não existe código que armazene credencial bancária; INV-16 como contrato futuro.

## Impacto em SI/LGPD

Sem credencial bancária armazenada ou solicitada, em nenhuma circunstância.

## Revisão

Revisar quando a importação de extratos entrar no escopo.
