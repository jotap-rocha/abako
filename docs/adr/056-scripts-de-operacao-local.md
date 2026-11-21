# 056 — Scripts de operação local: um comando `abako` com subcomandos (SPEC-015)

**Status:** Aceita
**Data:** 2026-11-20
**Autores:** dono do projeto (decisões 1 a 4), time (implementação e decisões 5 a 12)
**Reversibilidade:** alta (scripts novos; nenhuma tabela, migração nem contrato de API muda)

---

## Contexto

O ADR 022 previu `scripts/deploy-local` ("manual, recusa sem backup recente"), mas a operação do
dia a dia (subir banco e API, refazer o front, atualizar, migrar, fazer backup) era um conjunto de
comandos soltos. Já houve front antigo servido porque ninguém rodou o build, contêiner do banco
fora do ar e a letra do drive em minúsculo quebrando o Vitest. O ADR 019 e o ADR 024 mandam que
operação no `prd` dependa de decisão humana; o ADR 025 fixa o Alembic em SQL puro; o ADR 037 fixa
o backup cifrado.

## Decisão

Do dono (2026-11-20):

1. **Um comando só com subcomandos** (`abako <subcomando>`, com `ajuda`): `status`, `subir [--tst]`,
   `parar`, `reiniciar`, `build`, `atualizar`, `backup`, `migrar`, `pipeline`, `check`, `abrir`.
2. **Backup recente = até 7 dias** para operações que mexem no banco real; sem ele, `migrar` e
   `atualizar` (com migração pendente) recusam e mandam rodar `abako backup --alvo prd`.
3. **Sem início automático** com o Windows: nenhuma tarefa agendada nesta entrega.
4. **`subir` usa o banco real (`prd`) por padrão**, com aviso destacado (`AMBIENTE: PRD (dados
   reais)`); `--tst` usa o banco de teste.

Do time:

5. **A lógica é Python testável** (`scripts/operacao.py`). Tudo o que toca o sistema (processos,
   rede, terminal, relógio) passa por um objeto `Sistema` injetável; os testes usam um falso, sem
   Docker real e nunca o `prd`. Funções puras (build desatualizado, idade do backup, filtros)
   ficam separadas de quem executa.
6. **`scripts/abako.ps1` é um invólucro fino**: acha a raiz, põe a letra do drive em maiúsculo,
   entra na raiz, chama o Python da `.venv` e devolve o mesmo código de saída. Sem regra de
   negócio. UTF-8 com BOM (o Windows PowerShell 5.1 precisa) e compatível com o PowerShell 7.
7. **PID, ambiente e log da API em `%LOCALAPPDATA%\abako\`**, fora do repositório (`api.pid`,
   `api.log`). `parar` encerra só o PID guardado, depois de conferir que a linha de comando ainda é
   `python -m backend`; encerra a árvore daquele PID (o Python do venv lança o interpretador real
   como filho) e nada mais. Nunca derruba o banco. O log da API só é mostrado filtrado.
   Distinção importante: se o processo vive mas a linha de comando **não pôde ser lida** (o
   PowerShell falhou ou deu timeout), `parar` e `subir` recusam com "não consegui conferir o
   processo; tente de novo" e **mantêm** o `api.pid`; só quando a linha foi **lida** e não é do
   abako o PID é apagado e a recusa diz que pertence a outro programa.
   **Retenção do log:** `api.log` é sobrescrito a cada `subir` (não cresce sem limite e não guarda
   histórico) e a pasta tem a ACL padrão do perfil do usuário (só o próprio usuário e
   administradores); o script não ajusta permissões.
8. **Confirmação digitada e sem terminal = recusa.** `backup`, `migrar`, `pipeline` e `atualizar` no
   `prd` exigem que uma pessoa digite `PRD` num terminal interativo (`stdin.isatty()`); `migrar` e
   `atualizar` ainda exigem digitar `MIGRAR` depois de ver as revisões pendentes e de provar o backup
   de até 7 dias. Isso impede um agente de usar o script no `prd`. `ABAKO_CONFIRMA_PRD=sim` só entra
   no ambiente do processo **filho**, depois da confirmação, e é removida de qualquer ambiente
   herdado; nunca vai a arquivo. (Pedir `PRD` já no início, e não só ao migrar, é necessário porque
   até ler a versão do `prd` passa pelo guarda de alvo do ADR 019.)
9. **`status` não toca o `prd` por padrão** (DECISÃO DO AGENTE, **a confirmar pelo dono**; desvio
   da task, que pedia a versão do `prd` no `status`): a versão das migrações do `prd` só com
   `status --prd` (mesma confirmação digitada). O resto do `status` é só leitura. Alternativa se o
   dono preferir: o `status` ler a versão do `prd` sem digitar (é só leitura), ao custo de pôr
   `ABAKO_CONFIRMA_PRD=sim` no filho sem confirmação humana.
10. **Migração sempre para a revisão exata** (`alembic upgrade <rev>`, a que o `alembic heads`
    mostrou), nunca `head` às cegas; mais de uma cabeça recusa. `atualizar` e `migrar --alvo prd`
    só a partir da `main` (`atualizar` também exige árvore limpa e usa `git pull --ff-only`).
    **Mudança posterior à primeira versão:** a exigência de main vale **só para o prd**; no tst
    `migrar` roda de qualquer branch e apenas avisa a branch atual (uma migração nasce numa branch
    e é testada no tst antes de ir para a main). Se `atualizar` recusa por backup velho, a recusa
    ocorre depois do `git pull`, e a mensagem diz que o código já foi atualizado e que, depois do
    backup, se roda `abako atualizar` de novo.
11. **O script nunca abre o arquivo de variáveis.** O nome do contêiner, a pasta de backups e a
    porta vêm de um processo filho (`scripts/config_local.py`), que carrega as variáveis como os
    demais módulos do projeto e devolve só esses valores. **Porta:** `ABAKO_PORTA` do terminal (se
    houver) vale sobre a do projeto; vazia = 8080; só inteiro de 1 a 65535, senão erro claro
    ("ABAKO_PORTA inválida") sem repetir o valor.
12. **Códigos de saída:** 0 ok, 1 falha, 2 recusado por regra ou segurança. Mensagens de erro só
    com a classe da exceção e, se vier do psycopg, o SQLSTATE; saída de processo filho passa por um
    filtro (sem URL, senha nem linhas que carregam conteúdo de tabela). Erros de uso (subcomando ou
    opção inválidos) saem em português, com código 2.
13. **Executáveis fora do repositório.** O `shutil.which` do Windows procura primeiro na pasta atual;
    o script resolve `git`, `docker`, `npm`, `powershell` e `taskkill` por uma busca própria no
    PATH que ignora a pasta atual e qualquer pasta dentro do repositório (`procurar_executavel`),
    para um executável plantado no repositório não rodar no lugar do verdadeiro.
14. **`subir` no prd sem confirmação digitada: decisão consciente do dono (revisão de SI, R1).**
    Justificativa: o padrão `prd` com aviso destacado é o uso diário do app, e `subir` só inicia a
    API local; **o login por senha (ADR 020) impede que o agente obtenha uma sessão** e, sem ela,
    ele não lê nem escreve dado pela API. A trava forte (confirmação digitada + terminal
    interativo) fica nas operações que mexem no banco por fora da API: `backup`, `migrar`,
    `pipeline` e `atualizar`. **Risco residual declarado:** um agente com acesso ao shell consegue
    subir a API apontando para o `prd`, e a API fica à espera de login; nada é lido ou gravado sem
    sessão. **Alternativa de baixo custo, se o dono mudar de ideia:** exigir `PRD` digitado também
    ao subir no `prd` (uma chamada a `confirmar` em `Operador.subir`, sem tocar no resto).
15. **Backup medido pelo nome do arquivo (revisão de SI, R6).** A idade vem da data no nome e o
    arquivo precisa ter tamanho maior que zero. **Limitação:** o script não abre nem decifra o
    arquivo (só a chave pública existe no PC), então um arquivo falso com nome recente e conteúdo
    qualquer ainda é aceito; a checagem protege contra esquecimento, não contra adulteração.

## Alternativas consideradas

- **Tudo em PowerShell** ❌: difícil de testar e de manter para quem é forte em Python/SQL.
- **Tarefa agendada ou serviço do Windows** ❌ (fora de escopo; decisão 3).
- **`ABAKO_CONFIRMA_PRD` posta pelo próprio script no seu ambiente** ❌: contaminaria processos
  seguintes; só o filho a recebe.

## Dívidas e limites

- O terminal interativo é a barreira contra agente: um pseudo-terminal alocado de propósito ainda
  poderia digitar `PRD`. É uma barreira de processo, não de servidor (sem proteção server-side).
- O Windows PowerShell 5.1 come aspas duplas dentro de argumentos passados pelo `abako.ps1`
  (limitação do 5.1; o PowerShell 7 preserva). Nenhum comando do `abako` precisa delas.
- O `status` mostra commits atrás de `origin/main` sem `git fetch` (pode estar defasado).
- `reiniciar` e `atualizar` não instalam dependências do Python.

## Consequências

- Critérios `SPEC-015-AC-1` a `AC-9` em `tests/contracts/criterios.yaml`.
- Documentação de uso em `docs/operacao/subir-e-atualizar.md`.
- Sugestão para o próximo sync de contexto: citar `abako <subcomando>` no `CLAUDE.md`.

## Como verificar

`tests/test_operacao.py` (sistema falso) e `tests/test_abako_ps1.py` (PowerShell real, só com
subcomandos que não tocam banco nem Docker).

## Impacto em SI/LGPD

Nenhum dado novo é coletado ou guardado. Guardados em `%LOCALAPPDATA%\abako\`: PID, ambiente
(`tst`/`prd`), porta e o log da API (caminhos de requisição, sem corpo; o log não é impresso sem
filtro; sobrescrito a cada `subir`; ACL do perfil do usuário). O script não lê o arquivo de variáveis, não imprime senha, URL de conexão nem valor
financeiro, e a confirmação do `prd` fica restrita ao processo filho depois da digitação humana. A
leitura do `prd` pelo script (versão das migrações) segue o ADR 019: confirmação humana e sem
escrita fora das operações autorizadas.
