"""Guardrails da task 04 (ADR 024/032/037): backup, restauração e prd ficam com o usuário.

Regressão dos achados da revisão: `dropdb` via `docker exec` escapava do deny, e os
scripts de backup/restauração ligados a prd não passavam por nenhum `ask`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from config.agent_policies.contract import AgentPoliciesContract
from config.agent_policies.matcher import match_command

RAIZ = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def contrato() -> AgentPoliciesContract:
    return AgentPoliciesContract.load(RAIZ / "agent-policies.yaml")


@pytest.mark.parametrize(
    ("comando", "acao", "padrao"),
    [
        ("docker exec -it abako-postgres dropdb -U abako_admin restauracao", "deny", "dropdb"),
        ("dropdb -U abako_admin restauracao", "deny", "dropdb"),
        ("age-keygen -o E:\\abako-backup-chave.txt", "deny", "backup-chave-age"),
        ("type E:\\abako-backup-chave.txt", "deny", "backup-chave-age"),
        (
            "ABAKO_CONFIRMA_PRD=sim .venv/Scripts/python.exe -m scripts.backup --alvo prd",
            "ask",
            "confirma-prd",
        ),
        ("python -m scripts.resumo_banco --alvo=prd", "ask", "confirma-prd"),
        ("$env:ABAKO_CONFIRMA_PRD = 'sim'", "ask", "confirma-prd"),
        (
            "python -m scripts.restaurar --arquivo x.dump.age --identidade y.txt",
            "ask",
            "restaurar-backup",
        ),
        ("age -d -i chave.txt arquivo.bin", "ask", "age-decrypt"),
        ("age.exe --decrypt -i chave.txt arquivo.bin", "ask", "age-decrypt"),
    ],
)
def test_backup_e_prd_passam_pelo_usuario(
    contrato: AgentPoliciesContract, comando: str, acao: str, padrao: str
) -> None:
    decisao = match_command(comando, contrato)
    assert (decisao.action, decisao.pattern_id) == (acao, padrao)


@pytest.mark.parametrize(
    "comando",
    [
        "python -m scripts.backup",
        "python -m scripts.resumo_banco",
        "python -m scripts.backup --alvo tst",
        "age --version",
        "age-keygen --version",
        "python -m pytest tests/db/test_restore.py",
    ],
)
def test_fluxo_tst_e_versao_seguem_livres(contrato: AgentPoliciesContract, comando: str) -> None:
    assert match_command(comando, contrato).action == "allow"
