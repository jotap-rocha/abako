# 054 — Pipeline Postgres → DuckDB e analítico: convenções da SPEC-014

**Status:** Aceita
**Data:** 2026-11-13
**Autores:** time
**Reversibilidade:** média (o arquivo analítico é descartável e recriado a cada execução; a única
mudança no banco é a migração 0014, que só concede e revoga `EXECUTE`)

---

## Contexto

O ADR 008 fixou o analítico em DuckDB, arquivo separado, só agregados, fluxo unidirecional; o ADR 029
pediu `pg_advisory_lock`; os ADRs 045, 046, 047, 048, 049 e 052 deixaram o `abako_pipeline` sem
`EXECUTE` em quase tudo "até a SPEC-014". Faltava decidir o que o pipeline lê, como, e o que grava.
Decisões do usuário em 2026-11-13 (recomputo completo, disparo manual, sem tela).

## Decisão

1. **Fluxo (INV-15).** O pipeline lê o Postgres só pelo papel `abako_pipeline`, numa transação
   `REPEATABLE READ` **somente leitura** (um retrato consistente de todas as tabelas) e escreve só no
   arquivo DuckDB. Nenhum comando do pipeline escreve no transacional; o papel também não conseguiria.
2. **Recomputo completo, disparo manual.** Cada execução gera tudo de novo. CLI:
   `python -m pipeline [--alvo tst|prd] [--hoje AAAA-MM-DD] [--usuario N]...`. `--alvo` padrão é
   `tst`; `prd` exige `ABAKO_CONFIRMA_PRD=sim` no ambiente real e `ABAKO_DB_PIPELINE_URL_PRD`
   (mesmo guarda do ADR 019). Cada alvo tem o próprio arquivo (`analitico_tst.duckdb`,
   `analitico_prd.duckdb`). Sem agendador. `hoje` é a data civil em `America/Sao_Paulo`.
3. **Regra financeira fica no SQL (ADR 015).** O pipeline chama as funções existentes
   (`saldo_derivado`, `gasto_real_por_conta`, `fatura_resumo`, `limite_linha`, `reserva_situacao`,
   `a_receber_pessoas`, `r4_divergencias`); em Python só se enumeram usuários, contas, meses e
   competências a consultar. Para isso a **migração 0014** concede `EXECUTE` ao `abako_pipeline` em 15
   leituras `INVOKER` (as 7 acima e as auxiliares que elas chamam: `fatura_itens`, `mes_inicio`,
   `gasto_real`, `gasto_real_itens`, `reserva_nivel`, `reserva_cobertura`, `reserva_aporte`,
   `reserva_meses_ate`). Nenhum `SELECT` novo, nenhuma função de escrita, nenhuma de R2, vale,
   alertas ou `receita_*`. Isso **substitui**, só para essas funções, o "pipeline não executa" dos
   ADRs 045, 046 e 047.
4. **Tabelas do analítico** (todas com `user_id`; dinheiro `DECIMAL(18,2)`, nunca float):
   `saldo_diario` (conta, dia, saldo; do primeiro snapshot ou lançamento até hoje),
   `gasto_mensal` (mês, conta, gasto real), `fatura_resumo` (conta, competência, total, própria,
   terceiros), `limite_linha` (linha, limite, usado, disponível, em hoje), `cobertura_reserva` (uma
   linha por usuário, as colunas de `reserva_situacao`), `a_receber` (**só o total** por usuário) e
   `execucao` (hoje, versão do esquema, ambiente). O nome `a_receber_por_pessoa` do ADR 008 **não é
   usado**: nem o id da pessoa vai ao arquivo (ADR 045). Não há timestamp de geração, então o arquivo
   é determinístico para os mesmos dados.
5. **Só agregados e só ids.** Proibido levar `descricao`, nome de conta, de pessoa, de linha, de
   recorrente ou `login`, e qualquer linha de transação. As únicas colunas de texto são códigos curtos
   gerados pelo banco (`mes`, `competencia` AAAA-MM, `nivel`, `ambiente`). Os nomes são resolvidos na
   borda de quem lê, na sessão do dono (ADR 050), nunca no analítico.
6. **Troca atômica e falha.** O arquivo novo é gravado como `analitico_<alvo>.duckdb.<run>.tmp`,
   reaberto só para leitura e validado (contagens e somas contra o que foi lido; gasto do mês =
   `gasto_real`; fatura total = própria + terceiros). Só então `os.replace` o publica. Qualquer
   falha apaga o temporário e deixa o anterior intacto; restos de execução morta são limpos sob a
   trava. Se um leitor tiver o arquivo aberto no Windows, a troca falha (código 4) e o anterior fica.
7. **Limite honesto do papel.** O `abako_pipeline` tem `SELECT` de tabela inteira em `transacao_versao`
   (por isso nas views) e `conta_versao` desde a 0002, então **pode** ler `descricao` e `nome` da
   conta; `fatura_itens` devolve `descricao` por dentro de `fatura_resumo`. A garantia é de código e
   de teste: nenhuma consulta do pipeline cita esses campos (teste estático) e uma varredura do arquivo
   com marcadores sintéticos não os encontra. Restringir por coluna exigiria recriar as views; fica
   como endurecimento futuro, não nesta SPEC. `pessoa.nome` segue sem `SELECT` (ADR 045).
8. **Trava (INV-35, ADR 029).** `pg_try_advisory_lock(1094994767, 14)` (chave de duas partes, espaço
   distinto das travas `bigint` do ledger) numa conexão própria, tomada antes de criar pasta ou
   arquivo (o `mkdir` da pasta do analítico só roda sob a trava). A segunda execução sai com código 3 sem tocar em nada. A trava vale por sessão: cai se o
   processo morrer.
9. **Códigos de saída:** 0 ok; 2 configuração ou alvo recusado; 3 outra execução em andamento; 4
   falha (leitura, escrita, validação ou troca).
10. **Pasta do arquivo:** `ABAKO_ANALITICO_DIR`, recusada se estiver dentro do repositório; sem a
    variável, `%LOCALAPPDATA%\abako\analitico`. **A pasta não pode ser sincronizada nem compartilhada**
    (OneDrive, rede): o arquivo tem dado financeiro e a troca atômica pressupõe disco local. `*.duckdb` e `*.duckdb.wal` já estão no `.gitignore`;
    os temporários terminam em `.tmp` e ficam fora do repositório. `ABAKO_DUCKDB_PATH` do
    `.env.example` foi substituída.
11. **Logs (rule do pipeline):** `etapa`, `run_id`, `registros_lidos`, `registros_escritos`,
    `duracao_ms`; o R4 sai só como contagem (`R4: divergencias=N`). Em falha, só a classe do erro e o
    SQLSTATE: a mensagem do driver pode carregar valor ou nome e nunca é repetida. Sem traceback.
12. **Leitura:** `pipeline.ler.consultar(arquivo, tabela, user_id)` abre o arquivo com
    `read_only=True`, aceita só as seis tabelas de dados e **exige o `user_id`** (o da sessão, INV-13).
    CLI `python -m pipeline.ler`. Sem rota de API e sem tela nesta SPEC.
13. **Config e testes sem vazar senha.** `Config.url` fica fora do `repr`; uma URL malformada vira
    `ConfigInvalida` sem citar a URL; e `tests/conftest.py` mascara `://usuario:senha@` em todo
    relatório de falha do pytest (texto e seções capturadas).
14. **Dependência:** `duckdb==1.5.6` em `pipeline/requirements.txt` (incluído por
    `requirements-dev.txt`).

## Alternativas consideradas

- **Recalcular as regras em Python a partir das views** ❌: duplicaria a regra financeira e
  quebraria o ADR 015.
- **Incremental** ❌: volume pequeno; recomputo completo é mais simples e idempotente.
- **Trava por arquivo** ❌: o Postgres já está no caminho e a trava cai sozinha com a sessão.
- **A receber por pessoa** ❌: levaria um id de terceiro ao arquivo sem necessidade (ADR 045).

## Consequências

- Migração 0014 (só `GRANT`/`REVOKE EXECUTE`); testes antigos que afirmavam "pipeline sem EXECUTE"
  foram ajustados para a lista exata da 0014.
- Critérios SPEC-014-AC-1 a AC-12; fixtures F-PIPE-01/02; INV-15 e INV-35 ganham testes.
- A 0014 só foi aplicada em `tst`; **em `prd` depende de aprovação humana** (ADR 019).
- O pipeline não faz parte do `check`; os testes dele rodam em `tests/pipeline` (marcador `banco`).

## Premissas

Volume pequeno (dezenas de milhares de linhas de saldo diário); arquivo local; um leitor por vez.

## Fora de escopo

Painel/tela analítica, agendamento, incremental, restrição por coluna de `descricao`/`nome` para o
papel, exportação, qualquer API sobre o analítico.

## Como verificar

`tests/pipeline` (fluxo, idempotência, trava, troca atômica, agregados, log, papel, leitura,
config) e `tests/db/test_migracao_0014.py`.

## Impacto em SI/LGPD

Minimização: o arquivo guarda só ids numéricos, datas e agregados; nenhum nome, descrição ou login,
nem o id de pessoa. O `user_id` é preservado em toda linha e a leitura exige o da sessão (INV-13). O
papel não escreve em nada e a 0014 não lhe dá `SELECT` novo. O arquivo fica fora do repositório, com
as permissões da pasta do usuário, e nunca vai ao git, ao pacote do revisor ou a serviço externo. O
log não leva valor, nome, descrição nem id. Risco residual: o papel ainda pode, tecnicamente, ler
`descricao` e o nome da conta (item 7); a defesa é o código e os testes.

## Revisão

Revisar se o volume crescer, se surgir tela analítica ou se o papel for restringido por coluna.
