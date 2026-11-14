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
    parcelas: int | None = None,
    pessoa: int | None = None,
    bolso: str | None = None,
) -> tuple[int, int, bool]:
    """Cria ou edita; devolve (transacao_id, versao, criou_agora)."""
    linha = conn.execute(
        "SELECT transacao_id, versao, criado FROM lancamento_gravar("
        "%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
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
            parcelas,
            pessoa,
            bolso,
        ),
    ).fetchone()
    assert linha is not None
    return int(linha[0]), int(linha[1]), bool(linha[2])


def ano_atras(texto: str) -> str:
    """Desloca uma data ou competência ("2026-11-15", "2026-12") um ano para trás.

    As fixtures de cartão usam datas de 2026 que podem estar no futuro (o banco recusa compra
    com data futura, ADR 042); o deslocamento de um ano inteiro preserva mês, dia e a ordem.
    """
    return f"{int(texto[:4]) - 1}{texto[4:]}"


def linha_credito(
    conn: psycopg.Connection, user_id: int, nome: str, limite: str
) -> tuple[int, int]:
    """Cria uma linha de crédito; devolve (linha_id, versao)."""
    linha = conn.execute(
        "SELECT linha_id, versao FROM linha_credito_gravar(%s, NULL, NULL, %s, %s)",
        (user_id, nome, dec(limite)),
    ).fetchone()
    assert linha is not None
    return int(linha[0]), int(linha[1])


def cartao(
    conn: psycopg.Connection,
    user_id: int,
    nome: str,
    linha_id: int,
    fechamento: int | None = None,
    desde: str = "2026-01-01",
) -> int:
    """Cria a conta de dívida (cartão) e, se pedido, o primeiro dia de fechamento."""
    linha = conn.execute(
        "SELECT conta_id FROM conta_gravar(%s, NULL, NULL, %s, 'divida', NULL, %s)",
        (user_id, nome, linha_id),
    ).fetchone()
    assert linha is not None
    conta_id = int(linha[0])
    if fechamento is not None:
        fechar(conn, user_id, conta_id, fechamento, desde)
    return conta_id


def fechar(
    conn: psycopg.Connection, user_id: int, conta_id: int, dia_fech: int, desde: str
) -> None:
    conn.execute(
        "SELECT fechamento_gravar(%s, %s, %s, %s)", (user_id, conta_id, dia_fech, dia(desde))
    )


def compra(
    conn: psycopg.Connection,
    user_id: int,
    conta_id: int,
    data: str,
    total: str,
    parcelas: int,
    **extra: object,
) -> tuple[int, int, bool]:
    return lancar(conn, user_id, "credito", data, conta_id, total, parcelas=parcelas, **extra)  # type: ignore[arg-type]


def parcelas_da(conn: psycopg.Connection, user_id: int, transacao_id: int) -> list[tuple[str, str]]:
    """(valor, competencia) das parcelas vigentes, em ordem de parcela."""
    linhas = conn.execute(
        "SELECT valor, competencia FROM transacao_vigente "
        "WHERE user_id = %s AND transacao_id = %s ORDER BY parcela",
        (user_id, transacao_id),
    ).fetchall()
    return [(str(r[0]), str(r[1])) for r in linhas]


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
        for tabela in (
            "snapshot_saldo",
            "transacao_versao",
            "cartao_fechamento",
            "reserva_parametro",
            "vale_bolso",
            "vale_decisao",
            "vale_parametro",
            "recorrente_vinculo",
            "recorrente",
            "r2_parametro",
            "cartao_vencimento",
            "conta_versao",
            "linha_credito",
            "pessoa",
        ):
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
