# 001 — Sincronia de contexto no fechamento do fluxo

**Status:** Aceita  
**Data:** 2026-08-05  
**Autores:** time

---

## Contexto

`CLAUDE.md`, `AGENTS.md` e `CONTEXT.md` eram gerados uma única vez no bootstrap — por
`/install-harness` ou por `/harness-architect` na Fase 2 — e depois nenhum fluxo os tocava.

O levantamento no canônico mostrou:

- O DEV-LOOP persistia estado só em `PROGRESS_*.md` e `LOG_*.md`, arquivos efêmeros da task.
  Nada subia para o contexto durável.
- `harness-build` apenas **lia** o `CLAUDE.md` (para checar invariantes); `harness-ship` não o
  mencionava.
- A DoD (`rules/definicao-de-pronto.md`) cobrava gate, revisor, aceite, ADR e
  `metrics/entregas.jsonl` — nenhum critério sobre contexto.
- `/sync-context` era a única manutenção existente e era 100% manual: sem command, sem hook, sem
  invocação por nenhum agent. Disparava apenas por match do `description:`.
- `AGENTS.md` não estava nem na tabela de arquivos gerenciados da skill. O mandato "gere
  `AGENTS.md` sempre que gerar `CLAUDE.md`" valia só na geração, não na evolução — e o
  `AGENTS.md` do próprio canônico já havia divergido estruturalmente do `CLAUDE.md`.
- A documentação se contradizia: `docs/guia/03-harness.html` afirmava que o `/sync-context`
  atualizava o `CLAUDE.md` "automaticamente", o que nunca foi verdade.

Consequência prática: após algumas rodadas de `/dev`, o contexto descrevia um projeto que não
existia mais — e o agente da sessão seguinte partia de premissas falsas.

## Decisão

Vamos tornar a sincronização de contexto um **gate de fechamento de fluxo**, combinando processo
determinístico e automação de detecção:

1. **Critério 7 da DoD** — seção "Um FLUXO só está FECHADO quando", exigindo `/sync-context` no
   fechamento. Os 6 critérios por task ficam intactos.
2. **Passo obrigatório no `harness-ship`** (Fase 4) e **step 11 (SYNC)** no `dev-loop-executor`,
   este último só em `EXIT_COMPLETE`.
3. **Detecção automática** via `check_context_drift.py`, acionada por um hook de `Stop` que
   **avisa e nunca bloqueia**.
4. **`AGENTS.md` derivado por script** (`sync_agents_from_claude.py`), nunca editado à mão.

## Alternativas consideradas

### Opção A — Sincronizar a cada task ❌ Rejeitada

Rodar o sync no fechamento de cada task do `harness-build` e a cada iteração do Dev Loop.
Rejeitada porque a maioria das tasks é uma fatia vertical que não muda stack, serviço nem termo de
domínio: o relatório de drift viria vazio na quase totalidade das vezes, e o agente aprenderia a
ignorá-lo. Ruído destrói gate.

### Opção B — Sincronizar no fechamento do fluxo ✅ Escolhida

O sync roda uma vez por fluxo (`harness-ship` ou `EXIT_COMPLETE`), quando o acúmulo de mudanças
já é grande o suficiente para o relatório ter conteúdo real. Custo por fluxo, não por task.

### Opção C — Bloquear a sessão quando houver drift ❌ Rejeitada

Fazer o hook de `Stop` sair com código 2 (como o gate de ruff/mypy/pytest faz). Rejeitada porque
drift de documentação não é defeito de código: travar a sessão por doc desatualizada pune o
trabalho em progresso e incentiva contornar o hook. Além disso o `/sync-context` exige confirmação
humana antes de editar, então bloquear criaria um impasse em `--mode afk`.

### Opção D — Manter o `AGENTS.md` à mão com um checker de paridade ❌ Rejeitada

Um script que só acusasse divergência, deixando a correção manual. Rejeitada porque a divergência
já existia justamente por ser manual — o checker adicionaria trabalho sem remover a causa. A
derivação por script elimina a classe do problema; o que é genuinamente exclusivo do `AGENTS.md`
fica protegido entre `<!-- agents-only:start -->` e `<!-- agents-only:end -->`.

## Consequências

### Positivas

- Contexto desatualizado passa a ser detectável e cobrável, não uma questão de memória do usuário.
- `AGENTS.md` deixa de divergir do `CLAUDE.md` por construção.
- A detecção propaga de graça para projetos-filhos: os scripts moram dentro de
  `.claude/skills/sync-context/scripts/`, e o `stack_map.json` já copia a pasta inteira da skill.
- Projetos sem stack detectada passam a receber pelo menos o hook de drift — antes o
  `generate_content(".claude/settings.json")` gerava `hooks` vazio nesse caminho.
- A contradição na documentação foi corrigida: o hook detecta, o `/sync-context` pede confirmação.

### Negativas / Tradeoffs

- Drift introduzido no meio de um fluxo longo só é cobrado no fechamento. É o preço aceito para
  não gerar ruído por task.
- A derivação do `AGENTS.md` normaliza divergências editoriais que existiam de propósito (negrito
  nos invariantes, lista de comandos em bullets em vez de bloco `bash`, "assistente" em vez de
  "agente"). O ganho de zero-drift foi considerado maior que a perda cosmética.
- Dois scripts Python passam a ser código real mantido no canônico, que hoje não tem suíte de
  testes própria.

### Riscos

- O hook de `Stop` roda no fim de toda sessão. Mitigado por três guardas: sai silencioso se o
  script não existir, usa stamp file com janela de 4h (`.claude/.context-drift-stamp`) e sempre
  termina com `exit 0`.
- A reescrita de paths do `AGENTS.md` poderia corromper o próprio invariante de espelhamento, que
  cita `.claude/{agents,skills,...}` de propósito. Mitigado por a reescrita ser **estrutural**: só
  casa `.claude/` seguido de um subdiretório espelhado conhecido, então a forma com chave e o
  `.claude/settings.json` ficam intactos.

## Impacto em SI/LGPD

Baixo, por desenho:

- `check_context_drift.py` lê apenas manifests de dependência (`requirements.txt`,
  `pyproject.toml`, `package.json`), `docker-compose.yml` e `.env.example` — **nunca** o `.env`.
- Do `.env.example` extrai só o **nome** da chave; nenhum valor entra no relatório, no JSON ou no
  log da sessão. Se um `.env` existir, o script registra explicitamente que o ignorou.
- Nenhum dos scripts escreve em banco de dados ou faz chamada de rede.
- `sync_agents_from_claude.py` só escreve no `AGENTS.md`, e apenas com `--apply`.
- Nenhum dado pessoal é lido, processado ou registrado.

## Revisão

Esta ADR deve ser revisada se:

- O volume de falsos positivos do `check_context_drift.py` fizer o aviso ser ignorado na prática —
  sinal de que a heurística precisa ficar mais estrita.
- Surgir demanda por sincronização durante o fluxo (ex.: fluxos de vários dias em que o drift
  intermediário atrapalha) — nesse caso reavaliar a Opção A com filtro de mudança estrutural.
- O `harness-iterate` passar a alterar `CLAUDE.md` diretamente, o que exigiria estender o gate
  para o meio do fluxo.
