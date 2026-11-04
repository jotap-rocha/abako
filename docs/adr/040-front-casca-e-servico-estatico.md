# 040 — Casca do front: servida pela API, cliente gerado e service worker enxuto

**Status:** Aceita
**Data:** 2026-11-04
**Autores:** time
**Reversibilidade:** fácil

---

## Contexto

A task 06 (SPEC-012, 1 de 5) cria o front. Faltava decidir como o navegador chega ao app e à
API na mesma origem (ADR 035), como o cliente TS acompanha o contrato (ADR 015) e como a PWA
guarda o mínimo sem violar o ADR 031.

## Decisão

- **Tudo da API sob `/api`** (`/api/auth/login`, `/api/contas`, `/api/openapi.json`). O que não
  é `/api` é a SPA: o FastAPI serve `frontend/dist` na mesma origem, devolve o arquivo se ele
  existe dentro do build e `index.html` para qualquer outra rota (as telas). `/api/*`
  desconhecido responde 404 JSON, nunca o HTML. Sem `dist/`, a API sobe sozinha. Os mesmos
  cabeçalhos de segurança (Host, `no-store`, CSP) valem para os estáticos.
- **Sem servidor de desenvolvimento separado** na v1: `npm run build:watch` reconstrói o
  `dist/` e a página é aberta em `http://abako.localhost:8080`. Assim não há CORS nem Origin
  extra para configurar.
- **Stack:** React 19, TypeScript 5.9 (não a 7.x, ainda recente demais), Vite 8, Vitest +
  Testing Library. Versões exatas no `package-lock.json`; instalação com `npm ci
  --ignore-scripts`. Sem roteador nem biblioteca de estado de servidor por enquanto: entram
  quando uma tela precisar (tasks seguintes).
- **Casca e padrão de tela:** `react-router` 7.18.4 (modo biblioteca). Layout com menu lateral
  (vira barra inferior no celular), topo e área de conteúdo (`layout/Casca.tsx`); páginas
  montadas com `Pagina`, `Cartao`, `Carregando`, `EstadoVazio` e `MensagemErro`
  (`ui/componentes.tsx`), que cobrem os quatro estados de UI. `paginas/Contas.tsx` é o modelo de
  página com dados da API (usa o cliente gerado, trata sessão vencida voltando ao login).
  Início, Lançamentos e Alertas são reservas "em breve". O visual é neutro e provisório,
  concentrado em tokens CSS (`estilos.css`) com modo escuro automático; o design do usuário
  troca os tokens, não a estrutura.
- **Servidor no `prd`:** com `ABAKO_ENV=prd` o servidor usa o banco `prd` com o mesmo papel
  `abako_app` (só o nome do banco muda em `ABAKO_DB_APP_URL`, que continua apontando para
  `tst` para os testes). Padrão `tst`.
- **Cliente gerado** com `@hey-api/openapi-ts` a partir de `frontend/openapi.json`, exportado
  do FastAPI por `python -m scripts.exportar_openapi`. As operações têm nome curto
  (`auth_login`, `contas_listar`) via `generate_unique_id_function`. Defasagem do contrato ou
  do cliente falha em `tests/contracts/test_cliente_openapi.py` (SPEC-012-AC-1). O código
  gerado nunca é editado à mão; a configuração (URL base, cabeçalho `X-CSRF-Token`) fica em
  `src/api/sessao.ts`, a única porta do front para a API de sessão.
- **Service worker escrito à mão** (`public/sw.js`), sem Workbox: guarda só a casca estática
  e **nunca** toca em `/api`. O logout apaga todos os caches (`src/pwa/cache.ts`),
  inclusive se o servidor não responder. Sem uso offline.
- **CSP restritiva intacta:** sem script nem estilo inline, sem fonte ou CDN externos, sem
  atributo `style` no JSX. A base visual (`estilos.css`) é provisória e neutra; o design vem
  do usuário.
- **Dinheiro:** só texto. `formatarMoeda` apenas reagrupa o texto decimal da API; um teste
  varre o código de produção atrás de `parseFloat`, `Number(`, `toFixed`, `Math.` e
  `Intl.NumberFormat` (SPEC-012-AC-3).
- **Auditoria de dependências:** `npm audit --omit=dev` está limpo. O gerador 0.99.0 traz
  `js-yaml` com 3 avisos de CPU quadrática (severidade alta), numa ferramenta que só roda no
  desenvolvimento e no CI lendo o nosso `openapi.json`, nunca YAML de terceiros e nunca no
  bundle. A 0.97.0 evitaria isso, mas tem um aviso moderado num modelo que vai para o código
  do navegador; ficou a 0.99.0. Reavaliar na próxima atualização do gerador.

## Alternativas consideradas

- Vite em porta própria com proxy para a API: exige CORS, Origin extra e `Host` do dev ❌.
- Prefixo `/api` só nas rotas novas: mistura de convenções e colisão com telas como
  `/contas` ❌.
- `vite-plugin-pwa` / Workbox: dezenas de dependências para um cache que não pode tocar na
  API ❌.
- TanStack Query e roteador já: sem tela que precise deles nesta task ❌.

## Consequências

- Mudar o contrato da API exige exportar o contrato e regerar o cliente (a checagem avisa).
- O `check` e o CI passam a exigir Node 22.22+ ou 24.15+ (exigência do jsdom 30; o CI usa a 24) e `npm ci` em `frontend/`.
- Todo caminho de teste e de cliente passou de `/auth/...` para `/api/auth/...`.
- O service worker usa **lista fechada** (`/`, `/assets/`, `/icone-*`, `/manifest.webmanifest`);
  telas, `/api` e o resto vão direto para a rede. Depois do logout ele segue ativo e volta a
  guardar a casca pública (sem dado do usuário); uma requisição em voo pode repovoar o cache
  logo após o `caches.delete`, o que não expõe nada. A casca pode ficar uma carga atrasada
  após um deploy (os ativos têm hash).
- `Cache-Control: no-store` vale também para os estáticos, o que dispensa o cache HTTP dos
  ativos; a v1 aceita esse custo (é local).
- A rastreabilidade de testes Vitest confere o título por texto (ignora comentários), mais
  frouxa que a checagem por AST dos testes Python: `describe.skip` não é detectado.
- A varredura anti-`number` do AC-3 é por padrões (`parseFloat`, `Number(`, `BigInt`, ...);
  não pega `+x` nem `x * 1`. Ampliar quando houver telas com valores.
- Caminho com byte NUL ou impossível no disco cai na SPA (200 com os cabeçalhos), nunca em 500.

## Como verificar

`tests/contracts/test_cliente_openapi.py`, `tests/backend/test_estatico.py`,
`frontend/src/login/Login.test.tsx`, `frontend/src/dinheiro.test.ts`.

## Impacto em SI/LGPD

Nenhum dado novo. O service worker não lê nem guarda resposta da API; o logout apaga os
caches; sem segredo no bundle (o token CSRF vive só em memória).
