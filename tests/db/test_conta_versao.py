"""Tipos de conta e edição versionada de conta (ADR 042)."""

from __future__ import annotations

import psycopg
import pytest

from tests.db.util_lancamento import Recusa, apagar_usuario, conta, corrida, lancar
from tests.db.util_saldo import novo_usuario

pytestmark = pytest.mark.banco


def _editar(
    conn: psycopg.Connection,
    uid: int,
    conta_id: int,
    versao: int,
    nome: str,
    tipo: str,
    mae: int | None = None,
) -> int:
    linha = conn.execute(
        "SELECT versao FROM conta_gravar(%s, %s, %s, %s, %s, %s)",
        (uid, conta_id, versao, nome, tipo, mae),
    ).fetchone()
    assert linha is not None
    return int(linha[0])


def _vigente(conn: psycopg.Connection, uid: int, conta_id: int) -> tuple[object, ...]:
    linha = conn.execute(
        "SELECT versao, nome, tipo, conta_beneficio, conta_mae_id FROM conta_versao "
        "WHERE user_id = %s AND conta_id = %s AND vigente",
        (uid, conta_id),
    ).fetchone()
    assert linha is not None
    return tuple(linha)


def test_caixinha_pertence_ao_banco_e_edicao_cria_versao(conn: psycopg.Connection) -> None:
    uid = novo_usuario(conn)
    banco = conta(conn, uid, "Banco A")
    caixinha = conta(conn, uid, "Banco A Caixinha")  # criada como corrente, por engano
    assert _vigente(conn, uid, caixinha) == (1, "Banco A Caixinha", "corrente", False, None)

    v2 = _editar(conn, uid, caixinha, 1, "Banco A Caixinha", "reserva", mae=banco)
    assert v2 == 2
    assert _vigente(conn, uid, caixinha) == (2, "Banco A Caixinha", "reserva", False, banco)
    linha = conn.execute(
        "SELECT count(*) FROM conta_versao WHERE user_id = %s AND conta_id = %s", (uid, caixinha)
    ).fetchone()
    assert linha is not None and linha[0] == 2

    with Recusa(conn, "AB409"):  # versão antiga
        _editar(conn, uid, caixinha, 1, "outro nome", "reserva", mae=banco)


def test_regras_da_conta_mae(conn: psycopg.Connection) -> None:
    uid = novo_usuario(conn)
    banco = conta(conn, uid, "Banco A")
    reserva = conta(conn, uid, "Reserva", "reserva", mae=banco)

    with Recusa(conn, "AB422"):  # corrente não pertence a outra conta
        conta(conn, uid, "x", "corrente", mae=banco)
    with Recusa(conn, "AB422"):  # a mãe precisa ser corrente
        conta(conn, uid, "y", "reserva", mae=reserva)
    with Recusa(conn, "AB422"):  # banco com caixinha ligada não deixa de ser corrente
        _editar(conn, uid, banco, 1, "Banco A", "investimento")
    with Recusa(conn, "AB422"):
        conta(conn, uid, "z", "poupanca")


def test_nome_repetido_e_beneficio(conn: psycopg.Connection) -> None:
    uid = novo_usuario(conn)
    vale = conta(conn, uid, "Vale", "beneficio")
    assert _vigente(conn, uid, vale)[3] is True  # conta_beneficio acompanha o tipo

    with Recusa(conn, "AB410"):
        conta(conn, uid, "vale")  # nome igual, sem diferenciar maiúsculas
    with Recusa(conn, "AB422"):
        conta(conn, uid, "   ")

    lancar(conn, uid, "debito", "2026-02-02", vale, "10.00")
    with Recusa(conn, "AB422"):  # com lançamentos, não sai do tipo benefício
        _editar(conn, uid, vale, 1, "Vale", "corrente")
    _editar(conn, uid, vale, 1, "Vale refeição", "beneficio")  # renomear pode


def test_destino_de_investimento_continua_investimento(conn: psycopg.Connection) -> None:
    uid = novo_usuario(conn)
    c = conta(conn, uid, "corrente")
    inv = conta(conn, uid, "corretora", "investimento")
    lancar(conn, uid, "investimento", "2026-02-02", c, "10.00", destino=inv)
    with Recusa(conn, "AB422"):
        _editar(conn, uid, inv, 1, "corretora", "reserva")


def test_conta_de_outro_usuario_nao_vira_banco(conn: psycopg.Connection) -> None:
    uid = novo_usuario(conn)
    outro = novo_usuario(conn)
    banco_alheio = conta(conn, outro, "Banco do outro")
    with Recusa(conn, "AB422"):
        conta(conn, uid, "Minha reserva", "reserva", mae=banco_alheio)


def test_duas_edicoes_de_conta_simultaneas(esquema: str) -> None:
    """A segunda edição espera a trava e recebe 409 (não 404) quando a primeira commita."""
    with psycopg.connect(esquema) as prep:
        uid = novo_usuario(prep)
        c = conta(prep, uid, "corrente")
        prep.commit()
    try:
        _, segunda = corrida(
            esquema,
            lambda a: _editar(a, uid, c, 1, "nome A", "corrente"),
            lambda b: _editar(b, uid, c, 1, "nome B", "corrente"),
        )
        assert segunda == "AB409"
        with psycopg.connect(esquema) as ver:
            assert _vigente(ver, uid, c)[:2] == (2, "nome A")
    finally:
        apagar_usuario(esquema, uid)


def test_editar_sem_versao_e_recusado(conn: psycopg.Connection) -> None:
    uid = novo_usuario(conn)
    c = conta(conn, uid, "corrente")
    with Recusa(conn, "AB422"):
        conn.execute("SELECT * FROM conta_gravar(%s, %s, NULL, 'x', 'corrente', NULL)", (uid, c))
