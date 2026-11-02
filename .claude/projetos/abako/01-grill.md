# abako — Grill

> **Atualizado em 2026-10-18**: decisões D1..D8 da revisão adversarial aprovadas (D2 parcialmente); itens [confirmar] de concorrência, idempotência, trava do pipeline e ciclo de vida/backup resolvidos; SPECs renumeradas (ver `02-prd.md`).

> Consolidado a partir do brainstorm do usuário. As decisões vivem nos ADRs 006–035 (`docs/adr/`); aqui ficam o checklist de completude, as decisões em uma linha e as lacunas.

## Checklist de completude

- [x] **Problema real:** o saldo é conferido manualmente em planilha; falta visão de gasto real e de folga do orçamento (ADR 006).
- [x] **Usuário:** uma pessoa (o próprio dono). `user_id` preparado para multiusuário futuro, não funcional (ADR 006, 012).
- [x] **Critérios de sucesso mensuráveis:** invariantes INV-01..37 e fixtures numéricas (`tests/contracts/`, `fixtures/`).
- [x] **Out of scope declarado:** ver `02-prd.md`.
- [x] **Restrições técnicas:** local-first, Windows 11, Docker, Android antigo só como futuro (ADR 014).
- [x] **SLA / performance:** sem SLA formal; volume pequeno (ADR 008). Se surgir necessidade, entra como evolução contínua.

## Decisões (uma linha cada)

| ADR | Decisão |
|---|---|
| 006 | Ledger com versões (SCD2), snapshot de saldo, `user_id`, cartão ≠ linha de crédito |
| 007 | Reserva = conta dedicada + meta em meses |
| 008 | Analítico em DuckDB (arquivo separado), só agregados, fluxo unidirecional |
| 009 | Terceiros: `pessoa` na transação; repasse abate o "a receber" |
| 010 | Entrada manual na v1; sem credencial bancária |
| 011 | 7 tipos de transação; parcelas por linha; limite pelo total |
| 012 | Modelo de dados; `NUMERIC`; data civil `America/Sao_Paulo` |
| 013 | Estorno integral vs. com parcelas pagas; fechamento com vigência |
| 014 | Local-first; bancos `prd`/`tst`; risco de dado real assumido |
| 015 | React+TS PWA, FastAPI, Postgres + DuckDB, pipeline Python, regra em SQL; SQLite rejeitado |
| 016 | Frota enxuta: `fin-frontend` + 3 KBs |
| 017 | Revisor adversarial externo, 1 passada + 1 reteste |
| 018 | `.env` + gitleaks; backup com age |
| 019 | Guardrails: deny / ask / papéis no banco |
| 020 | Argon2id, sessão no servidor, CSRF, CORS, rate limit |
| 021 | Testes: pytest, Hypothesis, Vitest+RTL, Playwright; comando `check` |
| 022 | Repositório público, CI sem segredos, deploy local manual |
| 023 | Reserva (níveis), R2, recorrentes e vale |

## Lacunas abertas (para o /grill-me)

1. ~~R5~~ — resolvido: alerta do vale quando o `resta` de um bolso fica negativo (ADR 023).
2. ~~Horizonte do R2~~ — resolvido: parâmetro com vigência, inicial 10 dias (ADR 023).
3. **Pendências externas** (não bloqueiam as SPECs iniciais): formatos de exportação dos bancos; datas de fechamento e semântica de limite dos cartões; disponibilidade do modelo revisor.
4. ~~SLA / performance~~ — resolvido: sem SLA formal; tratar como evolução contínua se surgir.
5. ~~Estrutura de pastas e Docker~~ — resolvido: estrutura em `CLAUDE.md`; Docker Desktop; contêiner Postgres dedicado ao projeto (ADR 014).
6. **Comando `check`** e script de rastreabilidade: definir na SPEC-001.
7. ~~Rules genéricas~~ — resolvido: `backend`, `frontend`, `testes` e `pipeline` adaptadas ao abako.

## Estruturação (harness-define, 2026-10-18)

Tipo **a** (aplicação/API) com pipeline local pequeno. Itens marcados **[confirmar]** são inferência dos ADRs, não decisão registrada; o usuário valida antes do `harness-design`.

### Objetivos (MoSCoW)

**MUST:** esquema base com garantias de concorrência/idempotência (SPEC-001); login com isolamento por `user_id` (002); ledger SCD2 com saldo derivado e snapshot (003-004); faturas, parcelas, limite e estorno (005-006); terceiros/repasse (007); gasto real correto (008, INV-04/05/11/20); reserva (009).
**SHOULD:** recorrentes e R2 (010); alertas R1/R2/R4 (011); frontend PWA online (012); vale com alerta R5 (013); pipeline Postgres→DuckDB e painel analítico (014, por último).
(Numeração conforme a reordenação aprovada em 2026-10-18; ver `02-prd.md`.)
**COULD:** instalação como PWA refinada; textos explicativos de termos (story 23) além do mínimo.
**Out of scope:** ver `02-prd.md` (§ Out of Scope).

### Pipeline Postgres→DuckDB — 10 perguntas

1. **Fontes:** só o Postgres local (`prd`/`tst`), lido por papel somente leitura (ADR 008, CLAUDE.md). Sem arquivos externos nem APIs.
2. **Schema:** estável e controlado pelo próprio projeto (Alembic em `db/migrations/`, ADR 025). Mudança de schema transacional exige ajuste do pipeline na mesma SPEC.
3. **Volume:** pequeno, uso pessoal (ADR 008). Backfill: **[confirmar]** recomputo completo dos agregados a cada execução, sem backfill incremental.
4. **Sensibilidade:** dado financeiro pessoal (LGPD). O analítico guarda **só agregados**, sem transação individual (story 26). **[confirmar]** agregados não carregam descrição livre nem nome de terceiros.
5. **SLA:** sem SLA formal (ADR 008, lacuna 4). **[confirmar]** disparo manual/local, sem agendador na v1 (CD e hospedagem fora de escopo).
6. **Consumidores do Gold:** o painel analítico do próprio usuário. Sem ML, sem API pública.
7. **Owner/notificação:** o próprio usuário. **[confirmar]** falha = saída de erro do comando + código de saída não zero; sem canal externo de alerta.
8. **Ambiente:** 100% local (Windows 11 + Docker Desktop, `127.0.0.1`). Sem cloud, sem Databricks, sem Spark; migração futura não prevista.
9. **Qualidade:** **bloqueante (fail, mantém o arquivo anterior):** pipeline escreveria no transacional (INV-15), falha de leitura, soma de agregados divergente do transacional, troca não atômica. **Log:** **[confirmar]** divergência do ledger (R4) apenas sinalizada, nunca corrigida (INV-03/09/23).
10. **Portabilidade:** `prd` vs `tst` por configuração (nomes via `COMPOSE_PROJECT_NAME`, conexão por `.env`); um arquivo DuckDB por ambiente. Multi-cliente: N/A.

### Gates Medallion / Databricks / Key vault

- Medallion (T1-T8, B/S/G): **N/A** — não há camadas bronze/silver/gold nem Spark (`00-ideia.md`).
- Runtime Databricks / AI-DEV-KIT: **N/A** — runtime local Python.
- Key vault / secrets cloud: **N/A — sem key vault**; segredos por `.env` fora do git + gitleaks (ADR 018).

### Especificações implícitas detectadas

- **1 Falha de dependência externa:** N/A — sem API de terceiros na v1 (ADR 010). Única dependência é o Postgres local; falha do pipeline mantém o arquivo DuckDB anterior (troca atômica).
- **2 Concorrência:** duas escritas simultâneas sobre o mesmo ledger/versão. **Resolvido (D4):** garantia de esquema na SPEC-001 (unicidade parcial da versão vigente + campo de versão para controle otimista). Pipeline: execução simultânea impedida por trava `pg_advisory_lock` (SPEC-014).
- **3 Idempotência:** pipeline reexecutável com mesmo resultado (recomputo completo + troca atômica). Lançamento duplicado por duplo clique/retry: **resolvido (D4)** chave de idempotência na criação, esquema na SPEC-001 e uso na SPEC-004.
- **4 Autenticação/Autorização:** coberta (ADR 020, INV-13); `user_id` sempre da sessão. Disparo do pipeline: só pelo dono, comando local.
- **5 Dados sensíveis não declarados:** `pessoa` (terceiros) e descrições livres são PII de terceiros; mascarar na UI e fora de logs (rule `seguranca`). Não vão ao analítico **[confirmar]**.
- **6 Abuso e limites:** rate limit no login (ADR 020). Limite de tamanho de payload e de importação: **[confirmar]** valor na SPEC-001/002 (ainda **[confirmar]**).
- **7 Auditoria:** coberta pelo SCD2 (histórico de versões, exclusão lógica). Falta decidir se mudança de parâmetros (horizonte R2, fechamento do cartão) tem vigência registrada: já prevista (ADR 013, 023).
- **8 Estados de erro:** **[confirmar]** erro financeiro/validação exibido em linguagem direta (story 23); sem retry automático no front para escrita.
- **9 Ciclo de vida:** exclusão é lógica; LGPD "direito ao esquecimento" do próprio dono: fora da v1 (uso pessoal). **Resolvido (D7):** backup criptografado com age (ADR 018), com teste de restauração e política mínima de retenção dentro da v1.
- **10 Contrato externo mudando:** N/A na v1 (sem integração). Formatos de exportação dos bancos ficam como pendência externa para quando houver importação.

## Critérios de sucesso mensuráveis

- Invariantes cobertas: 37 de 37 (INV-01..37) com fixture (ou teste de propriedade) e ao menos 1 teste; script de rastreabilidade retorna vazio.
- Critérios de aceite: 100% dos `SPEC-NNN-AC-N` com teste.
- `check` verde antes de qualquer revisão adversarial.
- Isolamento: 0 consultas sem filtro de `user_id` da sessão.
- Dinheiro: 0 ocorrências de float em dinheiro (banco, Python, JSON).
- Pipeline: reexecução produz agregados idênticos; divergência soma analítico vs. transacional = 0.

## Revisão adversarial externa (2026-10-18)

Dois revisores (Gemini e GPT) receberam só PRD + grill, sem ADRs/invariantes; parte das críticas já estava coberta. Texto bruto: `adversarial-gemini.md`, `adversarial-gpt.md` (não versionar).

**Já coberto (não procede):** estorno com parcelas pagas (INV-08, ADR 013); CSRF/CORS/SameSite (ADR 020); terceiros fora da sobra do R2 (INV-18/26); sobra do vale não move saldo (INV-25); valor monetário como texto no JSON (INV-14, ADR 012); R4 é alerta visível no app, não só log (o item 9 do pipeline fala só do log do pipeline).

**Procede — decisões D1..D8 APROVADAS pelo usuário em 2026-10-18 (D2 parcialmente, ver abaixo):**

> **Status:** D1 aprovada · D2 **aprovada parcialmente** (a regra vale; a DATA real de fechamento de cada cartão segue como pendência externa, sem bloquear SPECs: cadastro com vigência, ajustável, calibrado por snapshot de fatura, ADR 013) · D3 aprovada · D4 aprovada · D5 aprovada · D6 aprovada · D7 aprovada · D8 aprovada.
> **D1 (interpretação adotada, validar na SPEC-003):** saldo de data passada e histórico exibidos = visão corrigida hoje (versões vigentes); a visão "conhecida na época" fica disponível por consulta de auditoria via data de registro do SCD2; snapshot antigo que passa a divergir após edição retroativa é sinalizado pelo R4, nunca corrigido sozinho.
> **D2 (regra aprovada):** dia de fechamento inexistente no mês usa o último dia válido do mês; a SPEC-005 define se a compra no próprio dia do fechamento entra na fatura que fecha ou na seguinte.
> **D3 (nova ordem):** ver `02-prd.md` (login na 002; gasto real na 008; vale+R5 na 013; pipeline na 014).
- D1 [APROVADA] Edição retroativa vs snapshot (a mais grave): definir se o histórico exibido é o corrigido hoje ou o conhecido na época, e que snapshot antigo que passa a divergir é sinalizado pelo R4. SCD2 já guarda quando cada versão foi registrada.
- D2 [APROVADA PARCIALMENTE; data real de fechamento = pendência externa] Fechamento do cartão em dia inexistente (31 em fevereiro) e compra no próprio dia do fechamento (ADR 013 não define).
- D3 [APROVADA] Ordem das SPECs (numeração antiga, antes da renumeração): login (008) antes das rotas financeiras; R5 (011) junto do vale (013); pipeline (009) para o fim; gasto real sem SPEC própria (INV-04 na 003, INV-05 na 004).
- D4 [APROVADA] Concorrência como garantia de esquema na SPEC-001: unicidade parcial da versão vigente, campo de versão (controle otimista), chave de idempotência, trava (`pg_advisory_lock`) no pipeline.
- D5 [APROVADA] Compra dividida entre próprio e terceiro: v1 só 100% próprio ou 100% terceiro (declarar), e tratamento de repasse maior que a dívida.
- D6 [APROVADA] Segurança local: validação de Host (DNS rebinding), limpar cache da PWA no logout, limite do que a senha protege (outro acesso à conta do Windows).
- D7 [APROVADA] Backup com teste de restauração e política mínima de retenção entram na v1 (substitui "direito ao esquecimento fora da v1").
- D8 [APROVADA] PWA: instalável, online na rede local, sem lançamento offline (declarar). O gasto essencial é parâmetro manual (ADR 007); bruto vs. líquido resolvido no ADR 034.

**Rejeitado:** pipeline disparado por evento / série histórica no DuckDB (v1 manual); hash de terceiro no analítico (continua dado pessoal); remover DuckDB do escopo (ADR 008, usuário mantém, só adia); testes de mutação (opcional).

## Próximo passo

D1..D8 resolvidas. Restam **[confirmar]**: pipeline (backfill, agregados sem descrição/terceiros, disparo manual, falha por código de saída, R4 só log), dados sensíveis de terceiros, limite de payload, estados de erro. Usuário valida esses itens e decide sobre o adversarial judge. Depois, `harness-design` (PRD atualizado em `02-prd.md`).
