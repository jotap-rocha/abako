# abako — retrospectiva da implementação

Fechamento do fluxo em 2026-11-14. Cobre as tasks 12 a 21 (SPEC-006 a SPEC-014), feitas em uma
sequência só depois de as tasks 1 a 11 estarem entregues. Registro factual, sem dado pessoal.

## O que foi entregue

- **21 tasks, 14 SPECs**, todas em `tests/contracts/specs_entregues.yaml`. PRs #20 a #30; o `prd`
  está na migração **0014** (todas as migrações aplicadas com backup antes e aval do dono).
- Regras financeiras no SQL (estorno, terceiros, gasto real, reserva, R2, alertas, vale) e o front
  só exibe (ADR 015), com testes de resposta incoerente de propósito para provar isso.
- Pipeline analítico Postgres→DuckDB (recomputo completo, troca atômica, trava, só agregados).
- ADRs 044 a 054, fixtures calculadas à mão por SPEC, critérios com teste existente em todas.

## Números (de `metrics/entregas.jsonl`)

| Task | SPEC | Tentativas até verde | Bloqueantes do revisor | Ressalvas |
|---|---|---|---|---|
| 12 | 006 | 2 | 0 | 15 |
| 13 | 007 | 3 | 1 | 11 |
| 14 | 008 | 3 | 1 | 13 |
| 15 | 009 | 2 | 0 | 11 |
| 16 | 010 | 4 | 2 | 21 |
| 17 | 011 | 2 | 0 | 11 |
| 18 | 012 (4/5) | 2 | 0 | 18 |
| 19 | 012 (5/5) | 3 | 0 | 13 |
| 20 | 013 | 4 | 2 | 24 |
| 21 | 014 | 2 | 1 | 15 |

Sete bloqueantes no total, **todos corrigidos antes do merge**. Nenhuma task fechou com bloqueante em
aberto.

## O que funcionou

- **Especialista antes do código.** Consultar o `abako-especialista` e registrar ADR, fixtures e
  critérios antes de implementar evitou retrabalho de regra. As decisões do dono entraram em lote.
- **Revisão independente achou erro real.** Exemplos: fatura que sumia da sobra do R2 quando o
  vencimento era cadastrado com a data de hoje (task 16); pagamento com data futura abatendo antes
  da hora (task 16); divisão de compra aceita em silêncio por chave fora da lista (task 13); beco
  sem saída ao marcar o VR com histórico (task 20); frase "Nenhum alerta" falsa com R5 ativo (task 20).
- **Teste que prova o que promete.** Respostas incoerentes de propósito no front; propriedades
  Hypothesis com oráculo independente; testes de concorrência com duas conexões.
- **Migração só depois de estável.** Esperar os gates antes de aplicar no `prd` evitou ter de
  corrigir uma migração já aplicada (a 0013 foi reescrita duas vezes antes de ir).

## O que deu errado (e o que mudou)

1. **Segredo no output de um teste.** Uma falha de teste imprimiu a URL do papel `abako_pipeline`,
   com senha, no output de um agente. Correção: `Config.url` fora do `repr`, mensagens sem URL e
   mascaramento de `://usuario:senha@` nos relatórios do pytest (`tests/conftest.py`). Pendente do
   dono: rotacionar a senha do papel.
2. **Subagente leu o `.env`** (um `source` sem imprimir nada) na task 16. Passei a incluir a regra
   dura nos prompts; não repetiu.
3. **PRs empilhados com merge em squash geram conflito** nos PRs seguintes. Procedimento: numa cópia
   separada do repositório (`git worktree`), `merge origin/main -X ours`, conferir que a árvore é
   **idêntica** à validada, corrigir os hashes em `entregas.jsonl`, push normal.
4. **Letra do drive em minúsculo** (`d:`) quebra o Vitest (módulos duplicados). Entrar sempre por
   `D:/projetos/abako`. Está no `CLAUDE.md`.
5. **Teste instável** (`Casca.test`, 1 em 6): era corrida dentro do teste; corrigido com `waitFor`.
6. **Mudança de gate sem aval** (`testTimeout` 5 s para 20 s) feita por um agente; levei ao dono, que
   manteve (ADR 051).
7. **Relatórios de subagente perdidos** quando o agente chamou a ferramenta de relatório duas vezes;
   passei a conferir o estado real (git, `check`) em vez de confiar no relato.
8. **Script antigo do scratchpad executado por engano** duplicou critérios; revertido e verificado
   sem duplicata. Regra nos prompts: não rodar scripts antigos.

## Decisões do dono ao longo do fluxo

Estorno e "parcela paga" (FIFO por competência, ADR 044), bloqueio de edição depois do estorno,
repasse acima da dívida aceito, horizonte do R2 inclusivo, vale só no VR com "classificar antes",
nome de terceiro em claro na sessão do dono, `testTimeout` de 20 s, sem painel analítico.

## Dívidas e pendências abertas

- **Rotacionar a senha do papel `abako_pipeline`** (feito pelo dono, não pelo agente).
- O papel do pipeline lê as tabelas inteiras do ledger; a defesa é código e teste (ADR 054, item 7).
  Endurecer com views próprias do pipeline.
- "Crédito de estorno" e "estorno integral" reconhecidos por sinal e por texto no front; ideal é a
  API expor um campo de tipo (ADR 050 e 051).
- Reteste formal do revisor depois das correções da task 21 não foi feito (conferência pelo agente
  principal e pelos testes).
- Dias reais de fechamento e vencimento dos cartões: o dono cadastra pelo app.
- Pasta `.claude/projetos/abako/fluxo/` não rastreada: decidir entre versionar e ignorar.
- Itens de design do front (menu de 12 itens em tela estreita, visual final) ficaram para o dono.

## Próximos passos sugeridos

1. Rotacionar a senha e rodar o pipeline uma vez contra o `tst` (`python -m pipeline`).
2. Cadastrar fechamento e vencimento reais dos cartões e a conta VR pelo app.
3. Decidir o endurecimento por coluna do papel do pipeline e o campo de tipo nas faturas.
