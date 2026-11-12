# SPEC-009: reserva e cobertura

**Status:** done  
**Blocked by:** tasks/abako/14-gasto-real.md
**ADR:** docs/adr/047-reserva-cobertura-e-aporte.md

## What to build

Reserva = soma das contas de tipo `reserva` (várias caixinhas; investimento fica fora), com saldo
líquido, imposto acumulado e bruto (ADR 034), meta = N meses × gasto essencial (N inicial 3; N, gasto
essencial e data-alvo são parâmetros manuais com vigência, ADR 007), níveis (crítica < 50%, atenção
de 50% a < 100%, saudável >= 100%), falta, cobertura em meses (líquido ÷ gasto essencial, 2 casas,
meio-para-cima) e aporte mensal necessário até a data-alvo (opcional; arredondado para cima em
centavos). Gasto essencial ausente/zero = configuração pendente (não é alerta R1). Migração 0010:
tabela `reserva_parametro` (append-only, escrita só por `reserva_parametro_gravar`) e leituras
INVOKER (`reserva_situacao(p_user, p_hoje)` e helpers puros).

## Acceptance criteria

Fonte: `tests/contracts/criterios.yaml` (SPEC-009-AC-1..10).

- [x] SPEC-009-AC-1: cobertura = saldo líquido ÷ gasto essencial, 2 casas meio-para-cima (INV-12) — tests/db/test_reserva.py::test_cobertura
- [x] SPEC-009-AC-2: níveis mudam exatamente em 50% e 100% da meta (INV-17) — ::test_cortes_nivel
- [x] SPEC-009-AC-3: aporte mensal até a data-alvo (arredonda para cima; mês igual; passada; meta atingida) — ::test_aporte_mensal
- [x] SPEC-009-AC-4: líquido, imposto acumulado e bruto = líquido + imposto; cobertura sobre o líquido (INV-37) — ::test_bruto_liquido_f_res_03
- [x] SPEC-009-AC-5: reserva = soma das contas de reserva; investimento fora — ::test_soma_de_reservas_f_res_04
- [x] SPEC-009-AC-6: parâmetros com vigência (último `desde` não posterior a hoje; regravação vale; validações) — ::test_parametros_com_vigencia_f_res_08
- [x] SPEC-009-AC-7: gasto essencial ausente/zero = configuração pendente, sem nível nem cobertura — ::test_config_ausente_f_res_07
- [x] SPEC-009-AC-8: isolamento por user_id (INV-13) — ::test_isolamento_por_user_id
- [x] SPEC-009-AC-9: papéis, SECURITY DEFINER, mensagens literais, downgrade da 0010
- [x] SPEC-009-AC-10: rotas da API (situação com `hoje` em America/Sao_Paulo; gravar/ler parâmetros)

## Notes

- Banco e API (feitos): migração 0010, rotas `GET /api/reserva`, `GET`/`PUT /api/reserva/parametros`, fixtures F-RES-03..08, testes em `tests/db/test_reserva*.py`,
  `test_migracao_0010.py` e `test_papeis.py::test_reserva_papeis`.
- **Contrato da API (implementado):** `GET` da situação passa `hoje` = data civil em `America/Sao_Paulo`
  (injetável para teste) e devolve dinheiro em texto; rota para gravar parâmetros chamando
  `reserva_parametro_gravar` (user_id da sessão, CSRF, AB422 -> 422, AB404 -> 404); rota para ler
  os parâmetros vigentes (view `reserva_parametro_vigente`); regenerar o cliente OpenAPI; valores
  fora do log.
- **Para o alerta R1 / front:** usar `nivel` (crítica/atenção/saudável) e `config_pendente`;
  nenhuma regra de nível, cobertura ou aporte fora do banco (ADR 015).
- Bruto e líquido decididos no ADR 034 (F-RES-03 criada à mão). Repasse, rendimento e aporte não
  são receita nem despesa (INV-12).

- **Para a task 18/19 (front):** `config_pendente: true` pede configuração (não é alerta R1) e vem sem nível, meta, falta, cobertura e aporte; `nivel` é `critica|atencao|saudavel|null`; a tela de parâmetros envia `meses`, `gasto_essencial` (texto), `data_alvo` opcional e `vigente_desde`.
