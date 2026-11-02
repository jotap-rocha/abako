# 038 — Login, sessão no Postgres e defesas da API

**Status:** Aceita
**Data:** 2026-11-02
**Autores:** time
**Reversibilidade:** moderada

---

## Contexto

A SPEC-002 materializa os ADRs 020, 031 e 035. Restam escolhas de implementação com custo de
mudança: onde ficam credencial e sessão, quem pode gravar senha, como limitar tentativas e como
formar o token CSRF.

## Decisão

- **Tabelas** (migração 0003): `credencial` (hash Argon2id, restrito a `$argon2id$`) e `sessao`.
  Nenhuma das duas é tabela de versão do ledger (ADR 036).
- **Senha só pelo comando local** (`python -m backend.cli criar-usuario|redefinir-senha`), que
  conecta como **dono** do banco e pede a senha sem eco. `abako_app` tem só `SELECT` em
  `credencial`: uma falha na API não consegue trocar senha. Mínimo de 12 caracteres.
  Redefinir derruba as sessões abertas do usuário.
- **Sessão:** o cookie `abako_sessao` (HttpOnly, `SameSite=Strict`, sem `Secure` porque a v1 é
  `http://` em localhost) carrega um token de 256 bits; o banco guarda **só o SHA-256**. Duração
  de 8 h fixa (sem renovação deslizante), configurável. `abako_app` tem `INSERT`/`DELETE` em
  `sessao` (logout e varredura de vencidas).
- **CSRF em três camadas:** `SameSite=Strict`; **Origin obrigatória e dentro da lista** em toda
  escrita (ausente também é recusada, inclusive no login); e **token por sessão** no cabeçalho
  `X-CSRF-Token` em toda escrita autenticada, comparado em tempo constante. O token é entregue
  no corpo do login e em `GET /auth/eu`.
- **Host (INV-34):** `TrustedHostMiddleware` com `abako.localhost`, `localhost` e `127.0.0.1`
  (a porta não conta). Outro Host: 400. CORS só com as origens derivadas dessa lista + porta.
- **Cabeçalhos:** `Cache-Control: no-store`, CSP sem `unsafe-inline`, `nosniff`,
  `Referrer-Policy: no-referrer`, em todas as respostas (inclusive a recusa de Host). `/docs` e
  `/redoc` desligados (usariam CDN, bloqueada pela CSP); `/openapi.json` permanece.
- **Rate limit de login:** 5 falhas por login em 15 min, em memória, janela deslizante; bloqueado
  responde 429 com `Retry-After`, mesmo com a senha certa. Login inexistente conta igual e
  gasta o mesmo tempo (hash falso), então não revela quem existe.
- **Servidor:** `python -m backend` escuta fixo em `127.0.0.1` e fixa o event loop Selector no
  Windows (o psycopg assíncrono não funciona no Proactor).

## Alternativas consideradas

- Biblioteca de rate limit (`slowapi`): dependência nova para um contador de 30 linhas ❌.
- Rate limit no Postgres: sobrevive a reinício, mas faz escrita a cada falha e exige `UPDATE` ❌
  (revisitar se o acesso deixar de ser só local).
- Token CSRF assinado e sem estado (double-submit): mais frágil que guardar na sessão, que já
  existe ❌.
- Cookie `Secure`: quebraria o login em `http://abako.localhost` até existir TLS local ❌.

## Consequências

- Reiniciar o processo zera o contador de tentativas (limite aceito; acesso é local).
- Um terceiro com acesso ao PC pode bloquear o login do dono errando a senha de propósito. Quem
  tem acesso à conta do Windows já está fora do que a senha protege (ADR 031).
- O limitador reserva a tentativa antes de verificar a senha (rajadas paralelas não furam o
  limite) e zera no sucesso. Ele é por login, sem teto de chaves: quem varrer logins inventados
  faz o dicionário crescer até o reinício. Aceito pelo acesso ser local.
- Sem `Secure` no cookie: se um dia houver TLS (ADR 031), passa a `secure=True`.
- Sessão expira de forma absoluta (8 h), sem ociosidade e sem teto por usuário; vencidas são
  varridas no login e no logout. O commit da sessão é explícito antes da resposta.
- `hosts_permitidos` e `origens_permitidas` recusam curinga e origem não local na validação.
- O R2 de autenticação scram do contêiner, antes previsto como ADR 038, passa a ser o **039**.

## Como verificar

`tests/backend/test_login.py`, `test_isolamento.py`, `test_host.py`, `test_csrf.py`,
`test_logs.py` e `test_cli.py` (SPEC-002-AC-1..5).

## Impacto em SI/LGPD

Senha, hash, token de sessão e token CSRF nunca vão para log (testado). O banco não guarda o
token do cookie. O `user_id` vem só da sessão. Nenhum dado pessoal novo além do `login`.
