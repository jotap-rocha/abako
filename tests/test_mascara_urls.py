"""A senha de uma URL de conexão nunca aparece em relatório de falha do pytest."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from tests.conftest import mascarar_relatorio, mascarar_urls

RAIZ = Path(__file__).resolve().parents[1]
SENHA = "SenhaSintetica123"
URL = f"postgresql://abako_pipeline:{SENHA}@127.0.0.1:5433/tst"


def test_mascara_so_a_senha() -> None:
    assert mascarar_urls(f"falhou em {URL} ok") == (
        "falhou em postgresql://abako_pipeline:***@127.0.0.1:5433/tst ok"
    )
    assert mascarar_urls("sem url aqui") == "sem url aqui"
    assert mascarar_urls("http://127.0.0.1:8080/x") == "http://127.0.0.1:8080/x"
    assert SENHA not in mascarar_urls(f"a={URL!r} b=postgresql+psycopg://u:{SENHA}@h/d")


def test_relatorio_de_falha_e_secoes_sao_mascarados() -> None:
    relatorio = pytest.TestReport(
        nodeid="x::y",
        location=("x.py", 1, "y"),
        keywords={},
        outcome="failed",
        when="call",
        longrepr=f"assert {URL!r} == 'outra'",
        sections=[("Captured log call", f"conectando em {URL}")],
    )
    mascarar_relatorio(relatorio)
    assert SENHA not in str(relatorio.longrepr)
    assert all(SENHA not in conteudo for _, conteudo in relatorio.sections)
    assert "***@" in str(relatorio.longrepr)


def test_saida_do_pytest_com_locais_nao_vaza_a_senha(tmp_path: Path) -> None:
    """Falha real num pytest filho, com --showlocals e --tb=long (os modos que vazariam)."""
    amostra = tmp_path / "test_amostra.py"
    amostra.write_text(
        "import logging\n\n"
        "def test_falha():\n"
        f"    url = {URL!r}\n"
        "    logging.getLogger('x').error('conexao %s', url)\n"
        "    assert url == 'outra'\n",
        encoding="utf-8",
    )
    saida = subprocess.run(
        [
            sys.executable, "-m", "pytest", "-q", "--tb=long", "--showlocals",
            "-p", "tests.conftest", "-p", "no:cacheprovider", "--rootdir", str(tmp_path),
            str(amostra),
        ],
        cwd=RAIZ, capture_output=True, text=True, check=False, timeout=120,
    )  # fmt: skip
    texto = saida.stdout + saida.stderr
    assert saida.returncode == 1, texto  # o filho falhou de verdade
    assert "test_falha" in texto
    assert SENHA not in texto
    assert "***@" in texto
