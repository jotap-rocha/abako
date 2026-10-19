# 028 — Ordem e renumeração das SPECs (001..014)

**Status:** Aceita
**Data:** 2026-10-19
**Autores:** time
**Reversibilidade:** fácil

---

## Contexto

A revisão adversarial apontou dependências invertidas: login depois de rotas financeiras, R5 antes do vale, pipeline antes das regras estabilizadas, gasto real sem entrega própria.

## Decisão

Ordem: 001 esquema base, `check`, concorrência/idempotência e backup; 002 login; 003 saldo e snapshot; 004 lançamento; 005 faturas; 006 estorno; 007 terceiros; 008 gasto real; 009 reserva; 010 recorrentes e R2; 011 alertas R1/R2/R4; 012 frontend; 013 vale e R5; 014 pipeline/analítico.
A migração de cada INV-xx está em `tests/contracts/invariantes.yaml`.

## Alternativas consideradas

Manter 001..013 ❌ (mantém as inversões).

## Como verificar

`scripts/validar_contratos.py` valida os campos `spec`.

## Impacto em SI/LGPD

Reordena o plano do PRD; não revoga ADR anterior.
