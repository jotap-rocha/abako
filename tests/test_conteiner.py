"""Partes puras de `db/conteiner.py`: publicação exata da porta, stderr sem dados de linha e
encerramento do produtor quando o consumidor não sobe. Sem banco e sem docker."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from db.conteiner import encadear, erro_seguro, publicacao_exata


@pytest.mark.parametrize(
    ("saida", "ok"),
    [
        ("127.0.0.1:5433\n", True),
        ("127.0.0.1:5433", True),
        ("127.0.0.1:5433\n0.0.0.0:5433\n", False),
        ("127.0.0.1:5433\n[::]:5433\n", False),
        ("0.0.0.0:5433\n", False),
        ("127.0.0.1:5432\n", False),
        ("", False),
    ],
)
def test_publicacao_exata_so_loopback_5433(saida: str, ok: bool) -> None:
    assert publicacao_exata(saida) is ok


def test_erro_seguro_descarta_valores_de_linha() -> None:
    # Valores inventados que imitam o que o pg_restore citaria de uma linha real.
    stderr = (
        b'pg_restore: error: COPY failed for table "transacao_versao": '
        b'ERROR:  invalid input syntax for type numeric: "1234.56-segredo"\n'
        b'CONTEXT:  COPY transacao_versao, line 7, column valor: "1234.56-segredo"\n'
        b"DETAIL:  Key (user_id, chave)=(1, chave-sintetica) already exists.\n"
        b"pg_restore: error: could not execute query: ERROR:  duplicate key value violates "
        b'unique constraint "x"\n'
        b"Command was: COPY public.transacao_versao (id, valor) FROM stdin;\n"
    )
    msg = erro_seguro(stderr)
    assert "segredo" not in msg and "1234.56" not in msg and "chave-sintetica" not in msg
    assert "line 7" not in msg and "CONTEXT" not in msg and "DETAIL" not in msg
    assert (
        msg == "pg_restore: error: could not execute query: ERROR:  duplicate key value "
        'violates unique constraint "…"'
    )


def test_erro_seguro_sem_erro_reconhecivel() -> None:
    assert erro_seguro(b"") == "-"
    assert erro_seguro(b'CONTEXT:  COPY t, line 1: "valor-sintetico"\n') == "-"
    assert erro_seguro(b"age: error: no identity matched any of the recipients\n") == (
        "age: error: no identity matched any of the recipients"
    )


def test_encadear_mata_produtor_se_consumidor_nao_sobe(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    criados: list[subprocess.Popen[bytes]] = []
    original = subprocess.Popen

    def espiao(*a: Any, **k: Any) -> subprocess.Popen[bytes]:
        p: subprocess.Popen[bytes] = original(*a, **k)
        criados.append(p)
        return p

    monkeypatch.setattr(subprocess, "Popen", espiao)
    produtor = [sys.executable, "-c", "import time; time.sleep(60)"]
    inexistente = [str(tmp_path / "nao-existe.exe")]
    with pytest.raises(OSError):
        encadear(produtor, inexistente)
    assert len(criados) == 1
    assert criados[0].poll() is not None, "produtor ficou vivo"
