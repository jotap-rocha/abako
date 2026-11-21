"""SPEC-015-AC-8: o invólucro `scripts/abako.ps1` normaliza o drive e repassa o código de saída.

Roda o PowerShell de verdade (Windows PowerShell 5.1 e/ou PowerShell 7), só com subcomandos
que não tocam banco nem Docker. Sem o executável no PATH o teste é pulado, com o motivo escrito.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
PS1 = RAIZ / "scripts" / "abako.ps1"
SHELLS = ["powershell", "pwsh"]


def _rodar(shell: str, script: str, *args: str) -> subprocess.CompletedProcess[bytes]:
    exe = shutil.which(shell)
    if exe is None:
        pytest.skip(f"{shell} não está instalado neste computador (teste só vale no Windows)")
    return subprocess.run(
        [
            exe,
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            script,
            *args,
        ],
        capture_output=True,
        stdin=subprocess.DEVNULL,
        timeout=120,
        check=False,
    )


def test_o_ps1_e_utf8_com_bom_para_o_powershell_5() -> None:
    assert PS1.read_bytes().startswith(b"\xef\xbb\xbf")  # sem BOM o 5.1 lê os acentos como ANSI


@pytest.mark.parametrize("shell", SHELLS)
def test_ajuda_roda_e_devolve_zero(shell: str) -> None:
    r = _rodar(shell, str(PS1), "ajuda")
    saida = r.stdout.decode("utf-8")
    assert r.returncode == 0, r.stderr.decode("utf-8", "replace")
    assert "operação local" in saida  # acento íntegro: a saída é UTF-8
    assert "subir [--tst]" in saida


@pytest.mark.parametrize("shell", SHELLS)
def test_passa_o_codigo_de_saida_do_python(shell: str) -> None:
    r = _rodar(shell, str(PS1), "subcomando-que-nao-existe")
    assert r.returncode == 2  # recusado: o mesmo código do Python


@pytest.mark.parametrize("shell", SHELLS)
def test_normaliza_a_letra_do_drive_para_maiusculo(shell: str) -> None:
    caminho = str(PS1)
    if len(caminho) < 2 or caminho[1] != ":":
        pytest.skip("caminho sem letra de drive: o teste só vale no Windows")
    minusculo = caminho[0].lower() + caminho[1:]
    r = _rodar(shell, minusculo, "raiz")
    assert r.returncode == 0, r.stderr.decode("utf-8", "replace")
    pasta = r.stdout.decode("utf-8").strip()
    assert pasta[0].isupper() and pasta[1] == ":"
    assert pasta == str(RAIZ)[0].upper() + str(RAIZ)[1:]


@pytest.mark.parametrize("shell", SHELLS)
def test_argumento_com_espaco_e_aspas_simples_chega_inteiro_ao_python(shell: str) -> None:
    r = _rodar(shell, str(PS1), "backup", "--alvo", "prd tst")
    assert r.returncode == 2
    assert "valor inválido para --alvo: 'prd tst'" in r.stderr.decode("utf-8", "replace")
    r = _rodar(shell, str(PS1), "it's um teste")
    assert r.returncode == 2
    assert "it's um teste" in r.stderr.decode("utf-8", "replace")


def test_aspas_duplas_chegam_inteiras_no_powershell_7() -> None:
    """O Windows PowerShell 5.1 come aspas duplas dentro de argumentos (limitação do 5.1, ver
    docs/operacao); nenhum argumento do abako precisa delas. O PowerShell 7 as preserva."""
    r = _rodar("pwsh", str(PS1), 'xy"z')
    assert r.returncode == 2
    assert 'xy"z' in r.stderr.decode("utf-8", "replace")
