# SPEC-012 (2/5): telas de saldo e snapshot

**Status:** done  
**Blocked by:** tasks/abako/06-front-casca.md, tasks/abako/07-saldo-snapshot.md

## What to build

Telas de saldo por conta, criar conta, informar snapshot e ver divergência, lista do R4 em Alertas, com textos explicativos em linguagem direta.

## Acceptance criteria

- [x] SPEC-012-AC-4: a tela mostra o saldo de cada conta vindo da API, sem recalcular (com carregando, vazio e erro) — tested by: frontend/src/saldos/Saldos.test.tsx::mostra_saldo_da_api (+ mostra_carregando_ate_a_api_responder, mostra_estado_vazio, mostra_erro_e_tenta_de_novo)
- [x] SPEC-012-AC-5: informar snapshot exibe a divergência retornada pela API — tested by: frontend/src/saldos/Snapshot.test.tsx::mostra_divergencia
- [x] SPEC-012-AC-6: jornada login → ver saldos — tested by: tests/e2e/test_saldos.py::test_login_e_saldos

## Notes

Design ditado pelo usuário (visual neutro por ora, tokens em `frontend/src/estilos.css`).

- A tela de Contas usa `GET /api/saldos` (já traz nome e benefício); `paginas/Contas.tsx` saiu.
- O valor digitado ("1.234,56") só tem os caracteres trocados para o formato da API (`lerValorDigitado`); quem aceita ou recusa é o servidor.
- Playwright entrou nesta task: Edge local (canal `msedge`, decisão do usuário: é o navegador que ele usa) e Chromium do Playwright no CI. O build do e2e vai para uma pasta temporária, nunca para `frontend/dist` (que o servidor do `prd` serve). O servidor do e2e roda fora da raiz e sem nenhuma `ABAKO_*` herdada.
- Textos de divergência citam lançamentos só como futuro: trocar quando as tasks 09/10 entregarem o cadastro.

### Dívidas registradas (revisões desta task)

- `Alertas.tsx` não descarta resposta atrasada (a tela de Contas já descarta).
- e2e: corrida pequena entre escolher a porta livre e o servidor subir; servidor órfão se o pytest for morto à força.
- `requirements-dev.txt` sem `--require-hashes` (como o resto do arquivo); o Chromium do CI fica amarrado só pela versão do Playwright.
- Glossário: "conta única de benefício" virou "pode haver mais de uma"; revisar ADR 023 e INVs do vale na SPEC-013.
