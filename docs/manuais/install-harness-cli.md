# Guia passo a passo — CLI do install-harness

Guia de referência para rodar `install_harness.py` diretamente no terminal, sem depender de uma
conversa com o Claude Code. Para o fluxo conversacional (dentro do Claude Code), veja
`.claude/skills/install-harness/SKILL.md`.

## Pré-requisitos

- Python 3.11+ (usa `tomllib` da stdlib pra parse de `pyproject.toml`/lockfiles — sem dependência externa)
- Path do canônico: **raiz deste clone** (default do launcher e do script). Override:
  `--canonical <path>` ou `HARNESS_CANONICAL`

## Modo rápido (recomendado) — `./install-harness`

Em vez de digitar o comando `python3` com o path completo, rode o launcher guiado a partir da raiz
do canônico. Este arquivo e o `install-harness` são ferramentas do canônico para instalar em
qualquer lugar — **não** são copiados para o projeto de destino; para atualizar um projeto já
instalado depois, volte aqui e rode `./install-harness` de novo apontando pro mesmo destino.

```bash
./install-harness
```

Ele pergunta, em ordem:
1. `1) Criar um projeto novo do zero` ou `2) Trazer o harness para um projeto já existente` —
   informativo/orientativo; o `install_harness.py` sempre detecta o estado real da pasta
   (`NOVO`/`SEM_HARNESS`/`ATUALIZAÇÃO`) sozinho, então essa escolha não muda o comportamento, só
   contextualiza o que vem a seguir.
2. Caminho do projeto de destino (Enter usa a pasta atual).
3. Forçar todas as categorias mesmo sem stack detectada `[s/N]` — responda `s` pra aplicar
   `--force-all` (ver seção abaixo); Enter/`n` mantém só o que foi detectado de verdade.

Depois disso, delega tudo — detecção, Install Plan, perguntas de conflito, confirmação final —
para o mesmo motor descrito abaixo. O launcher defaulta para o diretório onde ele vive; se
precisar apontar outro clone, use `HARNESS_CANONICAL=/outro/path ./install-harness`. Qualquer
flag extra passada pro launcher (`./install-harness --force-category langgraph`, por exemplo)
é repassada direto pro `install_harness.py`.

## Modo avançado — chamando `install_harness.py` direto (flags, `--json`, automação)

## 1. Instalar num projeto novo (pasta vazia ou inexistente)

```bash
# Na raiz deste canônico:
python3 .claude/skills/install-harness/scripts/install_harness.py \
  ~/meus-projetos/meu-projeto-novo
```

- Se a pasta não existir, a CLI pergunta se deve criar (`mkdir -p`).
- Detecta modo `NOVO` (sem `.claude/` ou vazia) → nenhum conflito, só imprime o Install Plan e pede
  confirmação final antes de escrever.
- Se o projeto já tiver dependência de uma lib conhecida (langgraph, supabase, qdrant/pgvector,
  langfuse, tenant/rls — a lista completa vive em `scripts/stack_map.json`,
  categorias `keyword_in_files`), a stack correspondente entra no plano automaticamente. **`pipeline_dados`
  é sempre instalada** (mesmo nível que foundation/dev_workflow). A detecção
  faz parse real de `pyproject.toml`/`package.json` (lista de dependências, não o arquivo inteiro) e
  também olha `uv.lock`/`poetry.lock`/`package-lock.json`/`requirements.txt` quando existem — um
  lockfile é sinal mais forte que o declarado, porque reflete o que de fato está instalado.

### Stack não detectada mas você quer instalar mesmo assim — `--force-category` / `--force-all`

Às vezes a stack ainda não está no `pyproject.toml`/`package.json` (projeto recém-iniciado, ou
dependência ainda não declarada) mas você já sabe que vai usar. Duas formas:

```bash
# força só as categorias específicas que quiser (repetível)
python3 .../install_harness.py ~/meu-projeto --force-category langgraph --force-category rag_vetorial

# força TODAS as categorias puladas de uma vez — não precisa listar nome nenhum
python3 .../install_harness.py ~/meu-projeto --force-all
```

Os nomes de categoria pro `--force-category` são os mesmos do `stack_map.json`
(`python_fastapi`, `langgraph`, `supabase`, `react_frontend`, `multi_tenant`, `observabilidade`,
`rag_vetorial`, `cloud_secrets`). `pipeline_dados` já entra sempre — não precisa forçar. Rode com `--dry-run` primeiro pra ver a lista de categorias
puladas (`Categorias puladas por falta de stack detectada: ...`) antes de decidir o que forçar —
ou pule direto pro `--force-all` se quiser tudo. No Install Plan, o item forçado aparece marcado
`[forçado — sem stack detectada]`, pra deixar claro que não foi detecção automática. Via
`./install-harness` (launcher guiado), o mesmo `--force-all` está disponível como pergunta
interativa (`Forçar todas as categorias...? [s/N]`), sem precisar decorar a flag.

> **Se você já tinha tentado `--force-category`/`--force-all` antes e não funcionou:** era um bug
> do próprio `./install-harness` (o wrapper bash não repassava argumentos extras pro script Python)
> — corrigido. Se ainda usa uma cópia antiga do launcher, atualize-a ou chame
> `install_harness.py` direto.

## 2. Atualizar um projeto que já existe (com ou sem harness)

```bash
# Na raiz deste canônico:
python3 .claude/skills/install-harness/scripts/install_harness.py \
  ~/meus-projetos/projeto-existente
```

- Sem `.claude/harness-manifest.json` → modo `SEM_HARNESS`: instala o que falta, **nunca** toca no
  que já existe sem perguntar.
- Com manifest → modo `ATUALIZAÇÃO`: só atualiza arquivos do canônico marcados `customized: false`
  (e só se o conteúdo realmente mudou); tudo com `customized: true` fica intocado, sem pergunta.

## 3. Ver o plano sem escrever nada

```bash
python3 .../install_harness.py ~/meu-projeto --dry-run
```

Mostra o Install Plan completo (o que seria copiado/gerado/pulado/mantido) e sai sem perguntar nem
escrever. Bom para conferir antes de rodar de verdade.

## 4. Quando aparecer um conflito

Um `CONFLICT` significa: o arquivo já existe no destino e **não** está protegido no manifest.
A CLI pergunta, um por vez:

```
CLAUDE.md já existe e não está rastreado no manifest (ou difere do canônico).
[k]eep  [o]verwrite  [d]iff  [m]erge manual (salva canônico como .harness-incoming)
[K]eep all restantes  [O]verwrite all restantes  [q] cancelar >
```

| Opção | O que faz |
|---|---|
| `k` | Mantém o arquivo do destino como está. Ele passa a ser `customized: true` no manifest — não será mais perguntado em atualizações futuras. |
| `o` | Substitui pelo conteúdo do canônico (ou pelo stub gerado, se for `CLAUDE.md`/`AGENTS.md`/`CONTEXT.md`/`HANDOFF.md`/`settings.json`). Fica `customized: false` — passa a receber updates automáticos. |
| `d` | Mostra o diff (unified diff) entre o arquivo atual e o canônico, depois pergunta de novo. |
| `m` | **Nunca mexe no original.** Grava a versão canônica ao lado, em `<arquivo>.harness-incoming`, para você reconciliar manualmente depois. |
| `K` / `O` | Aplica `keep`/`overwrite` a todos os conflitos restantes desta execução, sem perguntar de novo. |
| `q` | Cancela a instalação — nada é escrito. |

Depois de decidir todos os conflitos, a CLI mostra um resumo ("N artefatos serão tocados") e pede
confirmação final antes de aplicar qualquer coisa.

## 5. Rodar sem interação (automação/CI)

```bash
python3 .../install_harness.py ~/meu-projeto --yes
```

`--yes` nunca sobrescreve nada — todo `CONFLICT` vira `keep` automaticamente. Útil para rodar em
pipeline ou script, sabendo que o pior caso é "não instalou algo", nunca "sobrescreveu algo seu".

## 6. Modo `--json` (usado pela skill `/install-harness` dentro do Claude Code)

```bash
# 1. gera o plano em JSON, sem perguntar nada
python3 .../install_harness.py ~/meu-projeto --json > plano.json

# 2. você (ou o Claude) decide os conflitos e grava um JSON {path: resolution}
echo '{"CLAUDE.md": "keep"}' > decisoes.json

# 3. aplica com as decisões já tomadas
python3 .../install_harness.py ~/meu-projeto --json --decisions-file decisoes.json
```

`resolution` aceita `"keep"`, `"overwrite"` ou `"merge"` — mesmo significado da tabela acima.
Esse modo não usa `input()`, então serve tanto para automação quanto para ferramentas (como o
Claude Code) que não têm um TTY interativo real para repassar ao usuário.

## O que a CLI grava no destino

- **`.claude/`** — `agents/`, `skills/`, `kb/`, `rules/`, `commands/` (só os 3 arquivos raiz),
  `design/` e `sdd/` (scaffold de pastas), sempre respeitando a stack detectada para o que é
  condicional.
- **Arquivos gerados** (`CLAUDE.md`, `AGENTS.md`, `CONTEXT.md`, `HANDOFF.md`, `.claude/settings.json`)
  — stubs mínimos, sempre marcados `customized: true` (protegidos desde o início; refine com
  `/grill-me` e `/grill-with-docs` depois).
- **Arquivos de raiz do canônico** — `docs/manuais/harness-guide.md`, `docs/manuais/como-usar.md`, `.env.example`,
  `.gitignore`, `.mcp.json`, `requirements.txt` — copiados como estão. **Exceção:** `README.md`,
  `install-harness` e este próprio `docs/manuais/install-harness-cli.md` **nunca** são propagados — são material
  do canônico sobre como instalar, não conteúdo do harness.
- **`config/`, `docs/`, `metrics/`** — copiados inteiros, sempre (não são condicionados à stack).
- **`.cursor/`** — espelho estrutural de tudo em `.claude/` (incluindo `sdd/`), com as `rules/*.md`
  convertidas para o formato `.mdc` do Cursor. `settings.json` e `.mcp.json` não são espelhados
  para `.cursor/` (mas `.mcp.json` da raiz é copiado normalmente, como qualquer outro arquivo raiz).
- **`.claude/harness-manifest.json`** — registro de o que foi instalado e se está protegido
  (`customized`). É esse arquivo que faz o próximo `install_harness.py` saber o que pode
  atualizar sozinho e o que nunca deve tocar. Schema completo em
  `.claude/skills/install-harness/references/install-manifest-schema.md`.

## Depois de instalar

1. `/grill-with-docs` — preencher `CONTEXT.md` com a terminologia real do domínio
2. `/grill-me` — refinar `CLAUDE.md` com os invariantes do projeto
3. Revisar os hooks gerados em `.claude/settings.json` (comandos certos para a stack)
4. `/validar` — confirmar que o gate (ruff + mypy + pytest, ou eslint + vitest) está verde

## Referências relacionadas

- `.claude/skills/install-harness/SKILL.md` — fluxo conversacional dentro do Claude Code (usa esta
  mesma CLI em modo `--json`)
- `.claude/skills/install-harness/references/install-manifest-schema.md` — schema do
  `harness-manifest.json`
- `.claude/skills/install-harness/scripts/stack_map.json` — tabela stack → artefatos usada pela CLI
