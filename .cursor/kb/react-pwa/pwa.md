---
domain: react-pwa
topic: pwa
confidence: null
mcp_validated: null
---

# abako — PWA (ADR 015)

Explique os termos ao usuário (ele não domina web): **PWA** = site instalável; **manifest** = arquivo que descreve nome e ícones; **service worker** = script que cacheia arquivos.

- v1: Chrome desktop. Instalável via manifest (`name`, `short_name`, `start_url`, `display: standalone`, ícones 192 e 512, `theme_color`).
- Plugin sugerido: `vite-plugin-pwa` (confirmar versão atual). Estratégia: cachear só o **shell** (HTML/JS/CSS); dados da API **sempre da rede**.
- **Sem escrita offline no MVP:** sem fila de sincronização; offline mostra aviso claro e desabilita lançamentos.
- Nunca cachear respostas autenticadas com dado financeiro no service worker. **Logout limpa o cache** da PWA (ADR 031, SPEC-012).
- v1 é online, no navegador do mesmo PC (`127.0.0.1`); celular/rede local/externa exige ADR próprio.
- `localhost` conta como contexto seguro para instalar; Android/iOS só depois (a rede local exige HTTPS).
- Teste: Lighthouse/Playwright verificando manifest e registro do SW; atualização do SW não deve servir bundle velho indefinidamente.

> Texto escrito a partir dos ADRs do projeto. Versões e flags de ferramentas externas devem ser conferidas na documentação atual (context7) ao implementar; não foram validadas aqui.
