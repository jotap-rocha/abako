"""Chamadas às funções de escrita da 0005 (ADR 042), como a aplicação faz, para os testes."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal

import psycopg

from tests.db.util_saldo import dec, dia


def conta(
    conn: psycopg.Connection,
    user_id: int,
    nome: str,
    tipo: str = "corrente",
    mae: int | None = None,
) -> int:
    linha = conn.execute(
        "SELECT conta_id FROM conta_gravar(%s, NULL, NULL, %s, %s, %s)",
        (user_id, nome, tipo, mae),
    ).fetchone()
    assert linha is not None
    return int(linha[0])


def lancar(
    conn: psycopg.Connection,
    user_id: int,
    tipo: str,
    data: str,
    conta_id: int,
    valor: str | None = None,
    *,
    destino: int | None = None,
    bruto: str | None = None,
    imposto: str | None = None,
    descricao: str | None = None,
    transacao_id: int | None = None,
    versao: int | None = None,
    chave: str | None = None,
    hash_corpo: str | None = None,
) -> tuple[int, int, bool]:
    """Cria ou edita; devolve (transacao_id, versao, criou_agora)."""
    linha = conn.execute(
        "SELECT transacao_id, versao, criado FROM lancamento_gravar("
        "%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (
            user_id,
            transacao_id,
            versao,
            tipo,
            dia(data),
            None if valor is None else dec(valor),
            conta_id,
            destino,
            None if bruto is None else dec(bruto),
            None if imposto is None else dec(imposto),
            descricao,
            chave,
            hash_corpo,
        ),
    ).fetchone()
    assert linha is not None
    return int(linha[0]), int(linha[1]), bool(linha[2])


def excluir(conn: psycopg.Connection, user_id: int, transacao_id: int, versao: int) -> int:
    linha = conn.execute(
        "SELECT lancamento_excluir(%s, %s, %s)", (user_id, transacao_id, versao)
    ).fetchone()
    assert linha is not None
    return int(linha[0])


@dataclass(frozen=True)
class Versao:
    versao: int
    perna: int
    vigente: bool
    excluida: bool
    conta_id: int
    valor: Decimal


def versoes(conn: psycopg.Connection, user_id: int, transacao_id: int) -> list[Versao]:
    linhas = conn.execute(
        "SELECT versao, perna, vigente, excluida, conta_id, valor FROM transacao_versao "
        "WHERE user_id = %s AND transacao_id = %s ORDER BY versao, perna",
        (user_id, transacao_id),
    ).fetchall()
    return [Versao(*linha) for linha in linhas]


class Recusa:
    """Espera um erro de regra com o SQLSTATE dado (AB404, AB409, AB410, AB422).

    Roda dentro de um savepoint: o erro desfaz só a tentativa, não o cenário do teste.
    """

    def __init__(self, conn: psycopg.Connection, codigo: str) -> None:
        self.codigo = codigo
        self._tx = conn.transaction()

    def __enter__(self) -> Recusa:
        self._tx.__enter__()
        return self

    def __exit__(
        self, tipo: type[BaseException] | None, exc: BaseException | None, tb: object
    ) -> bool:
        self._tx.__exit__(tipo, exc, tb)  # type: ignore[arg-type]
        assert exc is not None, f"esperava recusa {self.codigo}, mas nada falhou"
        assert isinstance(exc, psycopg.Error), exc
        assert exc.sqlstate == self.codigo, (exc.sqlstate, str(exc))
        return True


def esperar_trava(observador: psycopg.Connection, pid: int, limite_s: float = 10) -> None:
    """Espera a conexão `pid` estar parada numa trava (pg_stat_activity), sem depender de tempo."""
    fim = time.monotonic() + limite_s
    while time.monotonic() < fim:
        linha = observador.execute(
            "SELECT wait_event_type FROM pg_stat_activity WHERE pid = %s", (pid,)
        ).fetchone()
        observador.rollback()  # cada leitura vê um retrato novo da atividade
        if linha is not None and linha[0] == "Lock":
            return
        time.sleep(0.05)
    raise AssertionError(f"a conexão {pid} não chegou a esperar a trava")


def apagar_usuario(url_dono: str, user_id: int) -> None:
    """Limpa o que um teste com dado commitado criou (teste de concorrência)."""
    with psycopg.connect(url_dono) as limpa:
        for tabela in ("snapshot_saldo", "transacao_versao", "conta_versao"):
            limpa.execute(f"DELETE FROM {tabela} WHERE user_id = %s", (user_id,))  # noqa: S608
        limpa.execute("DELETE FROM usuario WHERE user_id = %s", (user_id,))


def corrida(
    url_dono: str,
    primeira: Callable[[psycopg.Connection], object],
    segunda: Callable[[psycopg.Connection], object],
) -> tuple[object, object]:
    """A `primeira` grava sem commitar; a `segunda` roda em outra conexão e fica comprovadamente
    parada na trava; só então a primeira commita. Devolve (resultado 1, resultado 2 ou SQLSTATE)."""
    resultado: list[object] = []

    with (
        psycopg.connect(url_dono) as a,
        psycopg.connect(url_dono) as b,
        psycopg.connect(url_dono) as observador,
    ):
        r1 = primeira(a)

        def rodar_segunda() -> None:
            try:
                resultado.append(segunda(b))
                b.commit()
            except psycopg.Error as exc:
                b.rollback()
                resultado.append(exc.sqlstate)

        t = threading.Thread(target=rodar_segunda)
        t.start()
        esperar_trava(observador, b.info.backend_pid)
        a.commit()
        t.join(timeout=10)
        assert not t.is_alive(), "a segunda conexão não terminou"
    return r1, resultado[0]
