# Subir, parar e atualizar o abako (operação local)

Passo a passo do dia a dia no seu PC (Windows 11 + Docker Desktop). Um único comando, `abako`,
com subcomandos. Decisões e motivos: [ADR 056](../adr/056-scripts-de-operacao-local.md).

## Pré-requisitos (uma vez só)

1. **Docker Desktop aberto** (ícone da baleia na bandeja, "Engine running"). Sem ele o banco não sobe.
2. **Ambiente Python** criado na pasta `.venv` do repositório e **Node.js** instalado (o front usa o `npm`).
3. As variáveis de ambiente do projeto definidas no arquivo `.env` (só nomes em `.env.example`).
   O `abako` **nunca abre esse arquivo**: só os módulos do projeto o leem.
4. **Permissão para rodar scripts do PowerShell.** O Windows vem com `Restricted` (bloqueia `.ps1`).
   Uma vez, num PowerShell comum: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.
5. **Atalho `abako`** (opcional, recomendado). Abra o perfil do PowerShell com `notepad $PROFILE`
   (crie o arquivo se perguntar) e acrescente, trocando o caminho pelo do seu repositório:

   ```powershell
   function abako { & "D:\projetos\abako\scripts\abako.ps1" @args }
   ```

   Abra um PowerShell novo. Sem o atalho, use o caminho completo:
   `D:\projetos\abako\scripts\abako.ps1 status`. Daqui para a frente, `abako <subcomando>`.

Termos: **PowerShell** é o terminal do Windows; **perfil** é um arquivo que ele lê ao abrir;
**invólucro** (`abako.ps1`) é um script fino que só chama o Python do projeto.

## Subir o app

```powershell
abako subir          # usa o banco REAL (prd), com aviso em destaque
abako subir --tst    # usa o banco de teste (tst)
```

O que acontece, na ordem:

1. Sobe o banco (`docker compose up -d`) e espera ficar saudável (até 120 s).
2. Confere se o **build** do front está em dia; se não, refaz (veja abaixo).
3. Inicia a API em segundo plano, **só em `127.0.0.1`** (acessível apenas deste PC), sem janela presa.
4. Espera a API responder e mostra: `AMBIENTE: PRD (dados reais)` (ou `TST`) e `App: http://127.0.0.1:8080`.

Abra o endereço no Chrome, ou rode `abako abrir` (recusa se a porta estiver ocupada por outro
programa, para não abrir o navegador numa página que não é a do abako).

**Porta da API (`ABAKO_PORTA`).** Padrão 8080. Para mudar, defina `ABAKO_PORTA` no `.env` do projeto
(o `abako` a descobre por um processo do próprio projeto, sem abrir o arquivo) ou no terminal
(`$env:ABAKO_PORTA = "9090"`; o valor do terminal vale sobre o do `.env`). Vazia = 8080. Só vale um
número inteiro de **1 a 65535**; qualquer outra coisa (`abc`, `0`, `70000`) faz o comando falhar com
a mensagem "ABAKO_PORTA inválida", sem subir nada.

Onde ficam o número do processo (PID) e o log: `%LOCALAPPDATA%\abako\` (arquivos `api.pid` e
`api.log`), **fora do repositório**. Cole `%LOCALAPPDATA%\abako` na barra do Explorer para abrir.
O comando nunca imprime o log inteiro: se a API falhar ao iniciar, mostra só as últimas linhas, sem
URL de conexão nem senha.

Não há início automático com o Windows (decisão do dono): depois de reiniciar o PC, rode `abako subir`.

## O que é build, dist, PWA e cache

- **Front** é a parte que roda no navegador (telas). É escrita em TypeScript/React e precisa ser
  **compilada** para arquivos que o Chrome entende. Essa compilação é o **build** (`npm run build`).
- **`frontend/dist`** é a pasta que o build gera. A API serve essa pasta. Se ninguém refizer o build
  depois de mudar o código, o navegador mostra a **versão antiga**. O `abako subir` e o
  `abako atualizar` detectam isso: o build é considerado **desatualizado** se `dist/index.html` não
  existe ou se algum arquivo de `frontend/src`, o `package.json` ou o `openapi.json` é mais novo que ele.
- **PWA** (Progressive Web App) é um site que o Chrome pode instalar e que guarda cópias de
  arquivos no seu PC para abrir rápido. Quem guarda as cópias é o **Service Worker**; o conjunto de
  cópias é o **cache**.
- **Front antigo mesmo depois do build?** O cache do PWA pode estar servindo a cópia velha. No Chrome:
  `F12` (DevTools) -> aba **Application** -> **Service Workers** -> **Unregister**; depois, em
  **Storage**, **Clear site data**, e recarregue com `Ctrl+Shift+R`.

Para refazer só o front: `abako build` (roda `npm ci` se faltar `node_modules`, depois `npm run build`).

## Parar e reiniciar

```powershell
abako parar       # encerra SÓ a API que o abako iniciou (PID guardado); o banco continua de pé
abako reiniciar   # parar + subir, no mesmo ambiente
```

`parar` confere que o PID guardado ainda é a API do abako antes de encerrar. Se o número agora
pertence a outro programa, **recusa**, não encerra nada e remove o arquivo de PID velho. Se não
conseguir **ler** de quem é o processo (o PowerShell demorou ou falhou), recusa com "não consegui
conferir o processo; tente de novo" e **mantém** o PID: basta repetir o comando. Para desligar o banco, use o Docker Desktop.

## Ver a situação

```powershell
abako status
```

Mostra: banco (de pé e saudável?), API (porta e ambiente), versão das migrações do `tst`, idade do
último backup do `prd` (pela data no nome do arquivo), build em dia ou desatualizado, branch atual e
quantos commits está atrás de `origin/main` (sem `git fetch`; pode estar defasado). Nunca imprime
senha, URL de conexão nem valor financeiro. A versão do `prd` só com `abako status --prd`
(pede a confirmação digitada, veja abaixo).

## Atualizar (puxar o código novo)

```powershell
abako atualizar
```

Recusa se houver alterações não commitadas ou se a branch não for `main`. Depois: `git fetch`,
confirmação digitada, `git pull --ff-only` (só avança; nunca faz merge), compara a versão do banco
`prd` com a do repositório e, **se houver migrações pendentes**, mostra as revisões, exige **backup
do prd de até 7 dias** e uma segunda confirmação digitada (`MIGRAR`) antes de aplicar; refaz o build
se precisar e reinicia a API se ela estava rodando. Se o backup estiver velho, a recusa acontece
**depois** do `git pull`: a mensagem avisa "o código já foi atualizado (git pull feito); depois do
backup rode `abako atualizar` de novo". Se mudaram dependências do Python
(`requirements`), instale-as antes: o `abako` não mexe no `pip`.

## Backup, migração e pipeline

```powershell
abako backup --alvo prd     # backup cifrado do banco real (padrão sem --alvo: tst)
abako migrar --alvo prd     # aplica as migrações pendentes (padrão: tst; só a partir da main)
abako pipeline --alvo prd   # atualiza o analítico DuckDB (padrão: tst)
abako check                 # lint, tipos e todos os testes; leva uns 10 minutos
```

`migrar` sempre aplica a **revisão exata** mostrada (nunca `head` às cegas) e recusa se o
repositório tiver mais de uma cabeça de migração. No **prd** só roda a partir da `main`; no **tst**
roda de qualquer branch (uma migração nasce numa branch e é testada no tst) e apenas avisa a branch.
Sem backup do `prd` de até **7 dias**, `migrar` e `atualizar` recusam e mandam rodar
`abako backup --alvo prd`. A idade do backup vem da **data no nome** do arquivo e o arquivo precisa
ter **tamanho** maior que zero; o `abako` não abre nem decifra o arquivo, então um arquivo falso com
nome recente enganaria a checagem (limitação conhecida).

## Regra do prd: confirmação digitada, por uma pessoa

Qualquer operação que acessa o banco real (`backup`, `migrar`, `pipeline` e `atualizar`, mais
`status --prd`) pede que **você digite** `PRD` (e `MIGRAR` para aplicar migrações) num terminal
interativo. Em qualquer outra resposta, ou sem terminal interativo (script, agente, tarefa
agendada), o comando **recusa**. A variável `ABAKO_CONFIRMA_PRD=sim` só é posta no ambiente do
processo filho, depois da confirmação, e nunca em arquivo; se ela estiver no seu terminal, o
`abako` a remove dos filhos. `subir` usa o prd por padrão e só avisa (não pede digitação), porque
quem usa a API precisa fazer login com senha (ADR 020); a trava forte de digitação fica para as
operações que mudam ou copiam o banco (backup, migrar, pipeline, atualizar).

Códigos de saída: `0` ok, `1` falha, `2` recusado por regra de segurança.

Argumentos: espaços e aspas simples (`'`) passam inteiros pelo `abako.ps1`. **Aspas duplas (`"`)
dentro de um argumento** são comidas pelo Windows PowerShell 5.1 (limitação do próprio 5.1; o
PowerShell 7 preserva); nenhum comando do `abako` precisa delas.

## Solução de problemas

| Sintoma | O que fazer |
|---|---|
| "a porta 8080 já está ocupada por outro programa" | Outro programa usa a 8080. Feche-o, ou veja quem é: `netstat -ano` e procure a linha com `:8080` (o último número é o PID; `tasklist /FI "PID eq 1234"` diz o nome). O `abako` não encerra processos que não iniciou. |
| "docker compose falhou" / `Docker Desktop` | Abra o Docker Desktop, espere "Engine running" e repita. |
| "o banco não ficou saudável em 120 s" | Veja o contêiner no Docker Desktop (aba Containers -> logs). Porta 5433 (nunca 5432). |
| Tela antiga depois de atualizar | `abako status` (build em dia?), `abako build`, depois limpe o PWA: DevTools -> Application -> Service Workers -> Unregister. |
| "não foi possível executar 'npm'" | Instale o Node.js e abra um terminal novo. |
| `abako.ps1 não pode ser carregado porque a execução de scripts foi desabilitada` | Passo 4 dos pré-requisitos (`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`). |
| Vitest falha com módulos duplicados | O caminho foi digitado com `d:` minúsculo. O `abako` corrige sozinho; fora dele, entre por `cd "D:/projetos/abako"` (letra **maiúscula**). |
| "a API encerrou ao iniciar" | Leia as linhas mostradas; o log completo está em `%LOCALAPPDATA%\abako\api.log` (abra com cuidado: pode ter caminhos de requisição). |
| "o PID guardado agora pertence a outro programa" | Nada foi encerrado; o arquivo velho foi removido. Rode `abako subir`. |
