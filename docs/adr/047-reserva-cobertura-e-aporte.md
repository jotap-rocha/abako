# 047 — Reserva, cobertura e aporte: convenções da SPEC-009

**Status:** Aceita
**Data:** 2026-11-12
**Autores:** time
**Reversibilidade:** moderada (uma tabela de parâmetros e funções; o downgrade recusa se houver parâmetros)

---

## Contexto

Os ADRs 007, 023 e 034 definiram a reserva como conta dedicada com meta em meses de gasto
essencial, níveis e bruto/líquido, mas não a conta exata: quais contas somam, de onde vêm N e o
gasto essencial, como se calcula o aporte até a data-alvo. As decisões abaixo foram tomadas pelo
usuário em 2026-11-12.

## Decisão

1. **A reserva é a soma de todas as contas de tipo `reserva`** vigentes e não excluídas (várias
   caixinhas, ADR 042). Conta de investimento fica fora. Saldo = soma do `saldo_derivado` de cada
   uma, na data "hoje" informada: é o **líquido** (o que o banco credita). O tipo da conta é o
   **vigente na consulta**: uma conta que deixa de ser reserva sai da soma (saldo e imposto) e
   muda o passado calculado. É coerente com o gasto real (ADR 046 item 6) e aceito na v1.
2. **Imposto acumulado** = soma do `imposto` de todos os rendimentos vigentes e não excluídos nessas
   contas, com data até "hoje", desde o início dos lançamentos. **Bruto = líquido + imposto
   acumulado** (ADR 034). **Cobertura e nível usam o líquido** (INV-37). Rendimento em conta de
   investimento não entra.
3. **Meta = N meses × gasto essencial.** N (padrão 3 quando nunca informado, ADR 007) e o gasto
   essencial são **parâmetros manuais** do usuário, não derivados dos lançamentos.
4. **Níveis com cortes fixos** (INV-17): crítica se saldo < 50% da meta; atenção de 50% (inclusive)
   a < 100%; saudável se saldo ≥ meta. A comparação é exata (`saldo × 2 < meta`), sem arredondar.
   Isto fixa o que o ADR 023 chamava de "parametrizáveis": os cortes não são configuráveis na v1.
   **Falta** = max(meta − saldo, 0).
5. **Cobertura em meses** = saldo líquido ÷ gasto essencial, 2 casas, arredondada **meio-para-cima**
   (9000 ÷ 3000 = 3,00; empate 0,005 sobe para 0,01). A regra é `floor(x × 100 + 0,5) / 100`, também
   para saldo negativo (cobertura negativa): "meio-para-cima" é rumo a +∞, não "longe de zero".
   Efeito: −0,005 dá 0,00 (não −0,01), −0,015 dá −0,01 e −0,1667 dá −0,17.
6. **Gasto essencial ausente ou zero** = **configuração pendente**: cobertura, meta, nível, falta e
   aporte voltam nulos e `config_pendente = true`. Isso **não** é alerta R1 (nível crítico é
   alerta; pendência é pedido de configuração). O saldo, o imposto e o bruto continuam sendo
   devolvidos.
7. **Data-alvo é opcional** e também parâmetro com vigência. **Aporte mensal necessário** =
   falta ÷ meses, onde meses = diferença de meses civis entre o mês de hoje e o da data-alvo
   (`(ano_alvo − ano_hoje) × 12 + mês_alvo − mês_hoje`), mínimo 1, **arredondado para cima em
   centavos** (a soma dos aportes nunca fica abaixo da falta). Saldo ≥ meta → aporte 0,00. Data-alvo
   no mesmo mês → 1 mês (aporte = falta). Data-alvo de mês anterior ao de hoje → `alvo_vencida =
   true`, sem aporte (nulo; só a falta). Sem data-alvo → aporte nulo. Meta atingida com data-alvo vencida: aporte 0,00,
   `meses_ate_alvo` nulo e `alvo_vencida = false` (só a falta gera "vencida"; sem falta não há
   aporte a cobrar).
8. **Parâmetros com vigência, versionados** como o fechamento do cartão (ADR 043 item 5): tabela
   `reserva_parametro` append-only (`meses`, `gasto_essencial`, `data_alvo`, `vigente_desde`,
   `registrado_em`); a cada gravação vão os três valores juntos. Vale, para uma data, o registro de
   maior `vigente_desde` ≤ essa data; no mesmo `vigente_desde` vale o último gravado (view
   `reserva_parametro_vigente`). Gravar o que já vale para a mesma vigência é idempotente.
   Gravações simultâneas idênticas podem deixar duas linhas iguais (inofensivo: a view devolve o
   mesmo valor); não há trava para evitá-las.
   `vigente_desde` pode ser futuro (muda a partir daquele dia).
9. **Escrita só por função:** `reserva_parametro_gravar(p_user, p_meses, p_gasto_essencial,
   p_data_alvo, p_desde)`, `SECURITY DEFINER` com `search_path` fixo, `EXECUTE` só para `abako_app`.
   Valida: N de 1 a 120; gasto essencial ≥ 0 com até 2 casas e menor que 1 bilhão; `vigente_desde`
   ≥ 2000-01-01; data-alvo, se houver, ≥ 2000-01-01 (data passada é aceita: o estado
   "vencida" existe). Erros `AB422`/`AB404` com mensagem literal.
10. **Leituras `INVOKER` com `p_user`** (INV-13): `reserva_situacao(p_user, p_hoje)` devolve uma
    linha com `contas_reserva`, `saldo_liquido`, `imposto_acumulado`, `saldo_bruto`, `meses_meta`,
    `gasto_essencial`, `meta`, `nivel`, `falta`, `cobertura_meses`, `data_alvo`, `meses_ate_alvo`,
    `alvo_vencida`, `aporte_mensal`, `config_pendente`. **A data "hoje" é parâmetro** (determinismo);
    a API passa a data civil de `America/Sao_Paulo`. Helpers puros (`IMMUTABLE`): `reserva_nivel`,
    `reserva_cobertura`, `reserva_aporte`, `reserva_meses_ate`.
11. **Repasse, rendimento e aporte não são receita nem despesa** (INV-12): o aporte à reserva é
    transferência, o rendimento tem tipo próprio, o repasse é a receber. O gasto real e a receita de
    caixa (ADR 046) não mudam com eles; esta SPEC não altera esses cálculos.
12. **Papéis:** `abako_app` executa as funções e lê a tabela/view; `abako_pipeline` só `SELECT` na
    tabela e na view (como o fechamento), sem `EXECUTE`. Nenhuma agregação nova para o analítico foi
    inventada (SPEC-014 decide). Mensagens de erro literais (sem `||`), com teste estático.

## Consequências

- Migração 0010: uma tabela, uma view e funções. Downgrade recusa se houver parâmetros gravados
  (apagaria configuração do usuário); sem dados, remove tudo.
- Pendente de API (fin-backend): rotas de situação da reserva (`hoje` = data civil em
  `America/Sao_Paulo`, injetável) e de gravação/consulta dos parâmetros; dinheiro em texto; `user_id`
  da sessão; valores fora do log. O alerta R1 (SPEC posterior) decide a partir de `nivel`.
- O front só exibe: nenhuma regra de nível, cobertura ou aporte fora do banco (ADR 015).

## Alternativas consideradas

- Reserva = só uma conta ❌: o usuário tem várias caixinhas (ADR 042).
- Cobertura sobre o bruto ❌: o imposto já saiu; contradiz o ADR 034.
- Gasto essencial derivado dos lançamentos ❌: depende de categoria, que não existe (ADR 007).
- Cortes de nível configuráveis ❌: complexidade sem demanda; INV-17 fixa 50% e 100%.
- Parâmetros em tabela de versão com `vigente` e UPDATE ❌: o app não atualiza; o padrão
  append-only com vigência já existe no fechamento.
- Aporte arredondado para o centavo mais próximo ❌: podia ficar abaixo da falta.

## Fora de escopo

Alerta R1 e sua tela (consome `nivel`); categorização do essencial; IOF e outros tributos
(ADR 034, revisão); agregação no analítico (SPEC-014).

## Como verificar

INV-12, INV-17, INV-36, INV-37; fixtures F-RES-01 a F-RES-08; critérios SPEC-009-AC-1 a AC-10;
`tests/db/test_reserva.py`, `test_reserva_propriedades.py`, `test_reserva_mensagens.py`,
`test_migracao_0010.py`, `test_papeis.py`.

## Impacto em SI/LGPD

Dado financeiro pessoal (ADR 014). A tabela de parâmetros tem `user_id`; a escrita só passa pela
função `SECURITY DEFINER`, que recebe o `user_id` da sessão (INV-13), e o app não tem
`INSERT/UPDATE/DELETE` direto. As leituras filtram por `p_user`: com o `user_id` de outro usuário
devolvem zero/vazio. Mensagens de erro literais (sem valor, nome ou id); nada vai a log, URL ou
serviço externo. O pipeline recebe só leitura da tabela de parâmetros, sem função. Finalidade e
minimização inalteradas.

**Risco residual aceito:** as funções recebem `p_user` por parâmetro e não há RLS, como nas
migrações 0006 a 0009; a v1 é de um único usuário e o isolamento depende de a API passar o
`user_id` da sessão (INV-13). Revisar se o produto virar multiusuário.
