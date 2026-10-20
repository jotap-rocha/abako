# SPEC-001b: check, rastreabilidade e CI

**Status:** done  
**Blocked by:** tasks/abako/01-ambiente-banco.md

## What to build

Comando único `check` (lint, tipos, testes e rastreabilidade), script de rastreabilidade que lista invariantes e critérios sem teste (deve retornar vazio) e CI completo (Vitest, Playwright, Postgres efêmero) conforme `03-harness.md`. Versões exatas das dependências de frontend fixadas.

## Acceptance criteria

- [x] SPEC-001-AC-4: `check` roda lint, tipos, testes e rastreabilidade e falha se qualquer etapa falhar — tested by: tests/test_check.py::test_check_falha_quando_etapa_falha
- [x] SPEC-001-AC-5: o script de rastreabilidade lista invariantes/critérios sem teste e retorna vazio quando tudo tem teste — tested by: tests/test_rastreabilidade.py::test_lista_sem_teste
- [ ] SPEC-001-AC-6: o CI executa o `check` completo sem segredos — no test automático — verificado no primeiro run do workflow; waiver humano com o link do run

## Notes

Branch protection exige os checks depois do primeiro run.

### Fechamento

- Gate verde: `python -m scripts.check --com-banco` (ruff, mypy, pytest sem banco e com banco `tst`, contratos, rastreabilidade). Evidence-gate verde (`.claude/projetos/abako/evidencias/tasks/2.yaml`).
- **AC-6 (CI) = no test, waiver humano pendente.** Nenhum teste automático prova o run real. Prova local: `zizmor` limpo no workflow (actionlint indisponível localmente; roda no job `workflows` do CI). Depois do push: abrir a aba Actions do PR/branch, conferir que o job `check` ficou verde (inclui o service container Postgres em `127.0.0.1:5433`, `--com-banco`) e registrar aqui o link do run: `link do run: <preencher>`. Se o service container não aceitar `127.0.0.1:5433:5432` ou `test_escuta_apenas_localhost` falhar no runner, trocar por `docker run` num step.
- Regra pendente x quebrado (`scripts/rastreabilidade.py`): item sem teste cuja SPEC não está em `tests/contracts/specs_entregues.yaml` é pendente (aviso); com SPEC entregue, ou referência de teste inexistente, é quebrado (falha). `--estrito` falha com qualquer item sem teste (DoD final: saída vazia). Critério sem teste automático usa `waiver` no `criterios.yaml`. Hoje: 37 invariantes pendentes, 0 quebradas.
- Testes de banco ganharam o marcador `banco` (`pyproject.toml`); `check` roda `-m "not banco"` sempre e `-m banco` se `127.0.0.1:5433` responde (`--com-banco` exige; sem mock).
- Jobs de Vitest/Playwright: não criados (não há `frontend/`); documentado no cabeçalho do `ci.yml`. Aplicar setup-node fixado por SHA na task do frontend.
- Critérios SPEC-001-AC-1..6 adicionados em `criterios.yaml` (1..3 apontam os testes da task 01).
- Revisão independente (`revisor-codigo`): aprovado com ressalvas, 0 bloqueantes, 9 ressalvas (5 corrigidas no commit `fix(task-02)`: spec inválida, referência de teste estrita, waiver `humano:` visível, resumo do check com PULADO, SPEC completa exige `specs_entregues.yaml`; 4 em aberto).
