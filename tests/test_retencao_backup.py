"""Retenção 7 diários + 4 semanais (ADR 037) e remoção só dentro da pasta de backup.

Esperado calculado à mão (calendário de 2026): backups diários às 02:00 de 01/09 a 31/10 e
mais um às 14:00 de 31/10 (sábado, semana ISO 44 = 26/10 a 01/11).
- Diários (7 dias mais recentes com backup, o último de cada dia): 31/10 14:00, 30/10, 29/10,
  28/10, 27/10, 26/10, 25/10 (02:00). O de 31/10 02:00 expira.
- Semanais (4 semanas ISO anteriores à 44, o mais recente de cada, sempre domingo 02:00):
  sem. 43 -> 25/10 (já diário), sem. 42 -> 18/10, sem. 41 -> 11/10, sem. 40 -> 04/10.
Total mantido: 10 arquivos; os outros 52 (de 62) expiram.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from db.alvo import RAIZ, AlvoInvalido
from db.retencao import expirados, ler_nome, nome_backup, selecionar_retencao
from scripts.backup import aplicar_retencao, argumentos_recipient, pasta_backup


def test_aplicar_retencao_recusa_pasta_no_repo() -> None:
    with pytest.raises(AlvoInvalido):
        aplicar_retencao(RAIZ, "tst")


MANTIDOS_A_MAO = {
    datetime(2026, 10, 31, 14, 0),
    datetime(2026, 10, 30, 2, 0),
    datetime(2026, 10, 29, 2, 0),
    datetime(2026, 10, 28, 2, 0),
    datetime(2026, 10, 27, 2, 0),
    datetime(2026, 10, 26, 2, 0),
    datetime(2026, 10, 25, 2, 0),
    datetime(2026, 10, 18, 2, 0),
    datetime(2026, 10, 11, 2, 0),
    datetime(2026, 10, 4, 2, 0),
}


def _serie() -> list[datetime]:
    inicio = datetime(2026, 9, 1, 2, 0)
    return [inicio + timedelta(days=i) for i in range(61)] + [datetime(2026, 10, 31, 14, 0)]


def test_retencao_7_diarios_4_semanais() -> None:
    serie = _serie()
    assert len(serie) == 62
    assert selecionar_retencao(serie) == MANTIDOS_A_MAO


def test_retencao_com_lacuna_nao_apaga_tudo() -> None:
    # Dois backups antigos (sem. ISO 10 e 20) e um novo após meses parado: todos ficam.
    serie = [datetime(2026, 3, 2, 2, 0), datetime(2026, 5, 11, 2, 0), datetime(2026, 10, 31, 2, 0)]
    assert selecionar_retencao(serie) == set(serie)


def _dias(inicio: datetime, n: int) -> list[datetime]:
    return [inicio + timedelta(days=i) for i in range(n)]


def test_retencao_semanal_em_semanas_esparsas() -> None:
    """Diários 02:00 de 22/10 a 31/10/2026 (10 dias; 31/10 = semana ISO 44) e esparsos em
    03/08 (seg) e 05/08 (qua), ambos sem. 32; 15/07 (sem. 29); 10/06 (sem. 24); 20/05
    (sem. 21); 01/04 (sem. 14).
    - Diários: 25/10 a 31/10 (7). 22, 23 e 24/10 saem da camada diária.
    - Semanais (4 semanas com backup antes da 44): sem. 43 -> 25/10 (já diário); sem. 32 ->
      05/08 (03/08 expira); sem. 29 -> 15/07; sem. 24 -> 10/06. Sem. 21 e 14 ficam de fora.
    Mantidos: 10. Expiram: 22/10, 23/10, 24/10, 03/08, 20/05, 01/04.
    """
    esparsos = [
        datetime(2026, m, d, 2, 0) for m, d in [(8, 3), (8, 5), (7, 15), (6, 10), (5, 20), (4, 1)]
    ]
    serie = _dias(datetime(2026, 10, 22, 2, 0), 10) + esparsos
    esperado = set(_dias(datetime(2026, 10, 25, 2, 0), 7)) | {
        datetime(2026, 8, 5, 2, 0),
        datetime(2026, 7, 15, 2, 0),
        datetime(2026, 6, 10, 2, 0),
    }
    assert selecionar_retencao(serie) == esperado


def test_retencao_na_virada_do_ano_iso() -> None:
    """2026 tem semana ISO 53 (28/12/2026 a 03/01/2027). Diários 02:00 de 04/01 a 11/01/2027
    (8 dias; 11/01 = sem. 2 de 2027) e esparsos em 17/12 (sem. 51), 24/12 (sem. 52), 31/12/2026,
    01/01/2027 e 03/01/2027 (os três na sem. 53 de 2026).
    - Diários: 05/01 a 11/01 (7). 04/01 sai da camada diária.
    - Semanais: sem. 1/2027 -> 10/01 (já diário); sem. 53/2026 -> 03/01 (31/12 e 01/01 expiram,
      mesmo estando em anos civis diferentes); sem. 52 -> 24/12; sem. 51 -> 17/12.
    Mantidos: 10. Expiram: 04/01, 31/12, 01/01. Agrupar pelo ano civil separaria 31/12 e
    01/01 e manteria 31/12 no lugar de 17/12.
    """
    esparsos = [
        datetime(2026, 12, 17, 2, 0),
        datetime(2026, 12, 24, 2, 0),
        datetime(2026, 12, 31, 2, 0),
        datetime(2027, 1, 1, 2, 0),
        datetime(2027, 1, 3, 2, 0),
    ]
    serie = _dias(datetime(2027, 1, 4, 2, 0), 8) + esparsos
    esperado = set(_dias(datetime(2027, 1, 5, 2, 0), 7)) | {
        datetime(2027, 1, 3, 2, 0),
        datetime(2026, 12, 24, 2, 0),
        datetime(2026, 12, 17, 2, 0),
    }
    assert selecionar_retencao(serie) == esperado


def test_retencao_vazia() -> None:
    assert selecionar_retencao([]) == set()


def test_nome_sem_dado_pessoal_e_reversivel() -> None:
    nome = nome_backup("tst", datetime(2026, 10, 31, 14, 5, 9))
    assert nome == "abako-tst-20261031-140509.dump.age"
    assert ler_nome(nome) == ("tst", datetime(2026, 10, 31, 14, 5, 9))
    assert ler_nome("abako-tst-20261031-140509.dump.age.parcial") is None
    with pytest.raises(ValueError):
        nome_backup("restauracao", datetime(2026, 10, 31))


def test_remocao_so_na_pasta_e_so_no_padrao(tmp_path: Path) -> None:
    pasta = tmp_path / "backups"
    pasta.mkdir()
    for t in _serie():
        (pasta / nome_backup("tst", t)).write_bytes(b"x")
    # Outro ambiente, nome fora do padrão e subpasta: nunca são tocados.
    (pasta / "abako-prd-20260901-020000.dump.age").write_bytes(b"x")
    (pasta / "anotacoes.txt").write_bytes(b"x")
    (pasta / "sub").mkdir()
    (pasta / "sub" / "abako-tst-20260901-020000.dump.age").write_bytes(b"x")
    fora = tmp_path / "abako-tst-20260902-020000.dump.age"
    fora.write_bytes(b"x")

    removidos = aplicar_retencao(pasta, "tst")

    assert len(removidos) == 52
    restantes = sorted(a.name for a in pasta.iterdir() if a.is_file())
    esperados = sorted(nome_backup("tst", t) for t in MANTIDOS_A_MAO)
    assert restantes == sorted([*esperados, "abako-prd-20260901-020000.dump.age", "anotacoes.txt"])
    assert (pasta / "sub" / "abako-tst-20260901-020000.dump.age").is_file()
    assert fora.is_file()
    assert expirados(restantes, "tst") == []


def test_pasta_dentro_do_repo_recusada() -> None:
    for valor in [str(RAIZ), str(RAIZ / "backups"), "backups/abako"]:
        with pytest.raises(AlvoInvalido):
            pasta_backup({"ABAKO_BACKUP_DIR": valor})
    with pytest.raises(AlvoInvalido):
        pasta_backup({})


def test_recipient_recusa_chave_privada(tmp_path: Path) -> None:
    falsa = "AGE-SECRET-KEY-1" + "Q" * 58  # formato de chave privada, valor inventado
    with pytest.raises(AlvoInvalido, match="PRIVADA"):
        argumentos_recipient({"ABAKO_AGE_RECIPIENT": falsa})
    arq = tmp_path / "recipients.txt"
    arq.write_text(f"# comentário\n{falsa}\n", encoding="utf-8")
    with pytest.raises(AlvoInvalido, match="PRIVADA"):
        argumentos_recipient({"ABAKO_AGE_RECIPIENTS_FILE": str(arq)})
    with pytest.raises(AlvoInvalido):
        argumentos_recipient({"ABAKO_AGE_RECIPIENT": "nao-e-chave"})
    with pytest.raises(AlvoInvalido):
        argumentos_recipient({})
    publica = "age1" + "q" * 58
    assert argumentos_recipient({"ABAKO_AGE_RECIPIENT": publica}) == ["-r", publica]
