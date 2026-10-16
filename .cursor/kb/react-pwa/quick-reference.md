---
domain: react-pwa
topic: quick-reference
---

# React PWA — Quick Reference

| Assunto | Regra |
|---|---|
| Dinheiro | Texto ou decimal. Nunca `number`. Formatar só na exibição. |
| Cálculo financeiro | Nunca no front. Pedir endpoint ao backend. |
| Cliente da API | Gerado do OpenAPI; nunca chamada HTTP escrita à mão. |
| Formulário de lançamento | Dirigido pela matriz tipo → campos (7 tipos). |
| Categoria | Depende do tipo; grupo dentro da categoria. |
| Estabelecimento | Autocomplete. |
| Offline | Sem escrita offline no MVP. |
| Alvo da v1 | Chrome desktop, layout responsivo. |
| Tela principal | Receita de caixa, gasto real, sobra R2, reserva, alertas. **Sem vale.** |
| Testes | Vitest + RTL (componente); Playwright (poucas jornadas). |

## Termos para explicar ao usuário

PWA, service worker, manifest, Vite, CORS, CSRF, cookie HttpOnly, SameSite. Definições curtas em `CONTEXT.md`.
