# SPEC-015: scripts de operação local (subir, atualizar, build, backup, migrar)

**Status:** done  
**Blocked by:** tasks/abako/22-cadastro-cartao.md

## What to build

Um comando único com subcomandos, `.\scripts\abako.ps1 <subcomando>`, que automatiza a operação
do app no PC do dono. Fecha a lacuna do ADR 022, que prevê `scripts/deploy-local` ("manual, recusa
sem backup recente"), e evita problemas reais já vividos: front antigo servido porque ninguém rodou o
build, contêiner do banco fora do ar, letra do drive em minúsculo quebrando o Vitest.

A lógica fica em **Python testável** (`scripts/operacao.py`, no padrão de `scripts/backup.py`); o
`abako.ps1` é só um invólucro fino (normaliza o caminho com a letra do drive em **maiúsculo**, chama o
Python da `.venv` e repassa o código de saída).

Decisões do dono (2026-11-20), registrar no ADR 056:

- **Um comando só com subcomandos** (e `ajuda`).
- **Backup recente = até 7 dias** para operações que mexem no banco real; sem backup recente o script
  recusa e manda rodar `abako backup`.
- **Sem início automático** com o Windows (nenhuma tarefa agendada nesta task).
- Por padrão, `subir` usa o banco real (`prd`) e mostra um aviso destacado do ambiente; `--tst` usa o
  banco de teste.

Subcomandos:

- `ajuda`: lista os subcomandos e exemplos.
- `status`: contêiner do banco (de pé/saudável), porta da API, ambiente da API, versão das migrações
  do `prd` e do `tst`, idade do último backup do `prd`, se o build do front está desatualizado,
  branch atual e quantos commits está atrás da `main`. Nunca imprime senha, URL de conexão nem dado
  financeiro.
- `subir [--tst]`: sobe o Postgres (`docker compose up -d`) e espera ficar saudável; **refaz o build do
  front se estiver desatualizado** (compara o `dist` com `frontend/src`, `package.json` e
  `openapi.json`); inicia a API só em `127.0.0.1` em segundo plano (PID e log em
  `%LOCALAPPDATA%\abako\`, sem dado sensível); espera responder e imprime a URL. Recusa se a porta
  já estiver ocupada por outra coisa.
- `parar`: encerra **só** o processo da API que o script iniciou (pelo PID guardado); nunca derruba o
  banco nem outros processos.
- `reiniciar`: `parar` + `subir` com o mesmo ambiente.
- `build`: `npm ci` se faltar `node_modules`, depois `npm run build` do front.
- `atualizar`: recusa se a árvore de trabalho estiver suja ou se a branch não for a `main`; `git fetch`
  e `git pull --ff-only`; se houver migrações pendentes no `prd`, exige backup recente (≤ 7 dias) e
  confirmação humana digitada, depois migra; refaz o build; reinicia a API se ela estava rodando.
- `backup [--alvo prd|tst]`: chama `scripts.backup`; no `prd` exige a confirmação humana digitada.
- `migrar [--alvo prd|tst]`: mostra as revisões pendentes, exige backup recente no `prd` e confirmação
  humana digitada; só roda a partir da `main`.
- `pipeline [--alvo prd|tst]`: chama `python -m pipeline`; no `prd` exige a confirmação digitada.
- `check`: chama `scripts.check --com-banco` e avisa que leva uns 10 minutos.
- `abrir`: abre a URL do app no navegador.

Regras de segurança (ADR 019/024): operações no `prd` só com confirmação **digitada por uma pessoa**
no terminal (sem terminal interativo, recusam); `ABAKO_CONFIRMA_PRD=sim` só é posta no ambiente do
processo filho depois dessa confirmação e nunca em arquivo; o script **não lê o `.env`** (só os módulos
do projeto o carregam, como hoje); nenhuma senha, URL de conexão ou valor financeiro em saída, log ou
mensagem de erro.

Fora da task: tarefa agendada do Windows, tag e release, empacotamento em serviço, backup agendado,
acesso por celular ou rede, mexer em CI.

## Acceptance criteria

- [x] SPEC-015-AC-1: `subir` sobe o banco, refaz o build se o front estiver desatualizado, inicia a API só em 127.0.0.1 e mostra o ambiente (prd em destaque); recusa porta ocupada
- [x] SPEC-015-AC-2: o build desatualizado é detectado (front, package.json e openapi mais novos que o dist, ou dist ausente)
- [x] SPEC-015-AC-3: `status` mostra contêiner, porta, ambiente, versão das migrações, idade do backup, build e branch, sem segredo nenhum na saída
- [x] SPEC-015-AC-4: `parar` encerra só o processo que o script iniciou (PID guardado) e nada mais
- [x] SPEC-015-AC-5: `atualizar` recusa árvore suja ou branch fora da main, usa pull só fast-forward, e com migração pendente exige backup recente e confirmação digitada
- [x] SPEC-015-AC-6: operações no prd (backup, migrar, pipeline, atualizar com migração) exigem confirmação digitada e recusam sem terminal interativo; migrar e atualizar recusam sem backup do prd de até 7 dias
- [x] SPEC-015-AC-7: nenhuma senha, URL de conexão ou dado financeiro em saída, log ou erro, e o script não lê o .env
- [x] SPEC-015-AC-8: o invólucro normaliza o caminho com a letra do drive em maiúsculo e repassa o código de saída
- [x] SPEC-015-AC-9: documentação de uso em docs/operacao (passo a passo, com os termos de web explicados)

## Notes

Reaproveitar `scripts/backup.py`, `db/alvo.py` e o padrão de `scripts/check.py`. Testar a lógica em
pytest (sem Docker real quando possível: injetar o executor de comandos). Um teste de fumaça do
`abako.ps1 ajuda` com `powershell` é bem-vindo.

### Desvios e decisões da implementação (ADR 056)

- **`status` não consulta o prd por padrão** (DECISÃO DO AGENTE, a confirmar pelo dono): a versão das
  migrações do prd só com `abako status --prd`, que pede a confirmação digitada. Motivo: até
  `alembic current` no prd passa pelo guarda `ABAKO_CONFIRMA_PRD` (ADR 019). Desvio do texto da task.
- **`migrar` exige a `main` só para `--alvo prd`.** No tst roda de qualquer branch (a migração nasce
  numa branch e é testada no tst) e apenas avisa a branch. Muda o que a task dizia ("só roda a
  partir da main"). `atualizar` continua exigindo main e árvore limpa.
- `atualizar` com backup velho recusa depois do `git pull` e avisa que o código já foi atualizado.
- Porta da API: `ABAKO_PORTA` do terminal, senão a do projeto (lida por processo filho), senão 8080.
- `subir` no prd sem digitar `PRD` foi mantido por decisão do dono; justificativa e a alternativa de
  baixo custo estão no ADR 056, item 14.
