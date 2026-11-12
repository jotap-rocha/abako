"""Lançamentos. A regra (sinal pelo tipo, pernas, validações, versão) vive nas funções da
migração 0005 (ADR 042); aqui só se monta a chamada, sempre com o `user_id` da sessão (INV-13)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import psycopg


@dataclass(frozen=True)
class Dados:
    """O que o usuário informa num lançamento. `valor` é ignorado no rendimento."""

    tipo: str
    data: date
    valor: Decimal | None
    conta_id: int
    conta_destino_id: int | None
    bruto: Decimal | None
    imposto: Decimal | None
    descricao: str | None
    # Só na compra a crédito (1 a 48); o banco recusa nos demais tipos.
    parcelas: int | None = None
    # Compra a crédito de terceiro (100% da pessoa) ou repasse (obrigatória); o banco confere.
    pessoa_id: int | None = None


@dataclass(frozen=True)
class Lancamento:
    transacao_id: int
    versao: int
    tipo: str
    data: date
    valor: Decimal
    conta_id: int
    conta_destino_id: int | None
    bruto: Decimal | None
    imposto: Decimal | None
    descricao: str | None
    parcelas: int | None
    competencia: str | None
    # Só no estorno: compra estornada e crédito P emitido (ADR 044).
    estorno_de: int | None = None
    estorno_credito: Decimal | None = None
    # Compra de terceiro ou repasse: a pessoa (o nome vem de /pessoas, nunca daqui).
    pessoa_id: int | None = None


@dataclass(frozen=True)
class EstornoGravado:
    estorno_id: int
    competencia_credito: str
    total: Decimal
    pago: Decimal
    limite_devolvido: Decimal


def _texto(valor: Decimal | None) -> str | None:
    return None if valor is None else f"{valor:.2f}"


def hash_corpo(dados: Dados) -> str:
    """Hash do corpo canônico: "10" e "10.00" são o mesmo lançamento (INV-28)."""
    canonico: dict[str, object] = {
        "tipo": dados.tipo,
        "data": dados.data.isoformat(),
        "valor": _texto(dados.valor),
        "conta_id": dados.conta_id,
        "conta_destino_id": dados.conta_destino_id,
        "bruto": _texto(dados.bruto),
        "imposto": _texto(dados.imposto),
        "descricao": dados.descricao,
        "parcelas": dados.parcelas,
    }
    if dados.pessoa_id is not None:  # ausente quando nula: o hash antigo continua valendo
        canonico["pessoa_id"] = dados.pessoa_id
    texto = json.dumps(canonico, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


_SELECT = (
    "SELECT transacao_id, versao, tipo, data_transacao, valor, conta_id, conta_destino_id, "
    "bruto, imposto, descricao, parcelas, competencia, estorno_de, estorno_credito, "
    "pessoa_id "
    "FROM lancamento_vigente WHERE user_id = %s"
)


async def obter(
    conn: psycopg.AsyncConnection, user_id: int, transacao_id: int
) -> Lancamento | None:
    cur = await conn.execute(_SELECT + " AND transacao_id = %s", (user_id, transacao_id))
    linha = await cur.fetchone()
    return Lancamento(*linha) if linha else None


async def listar(
    conn: psycopg.AsyncConnection,
    user_id: int,
    *,
    conta_id: int | None,
    de: date | None,
    ate: date | None,
    limite: int,
) -> list[Lancamento]:
    sql = _SELECT
    params: list[object] = [user_id]
    if conta_id is not None:
        sql += " AND (conta_id = %s OR conta_destino_id = %s)"
        params += [conta_id, conta_id]
    if de is not None:
        sql += " AND data_transacao >= %s"
        params.append(de)
    if ate is not None:
        sql += " AND data_transacao <= %s"
        params.append(ate)
    sql += " ORDER BY data_transacao DESC, transacao_id DESC LIMIT %s"
    params.append(limite)
    cur = await conn.execute(sql, params)
    return [Lancamento(*linha) for linha in await cur.fetchall()]


async def gravar(
    conn: psycopg.AsyncConnection,
    user_id: int,
    dados: Dados,
    *,
    transacao_id: int | None = None,
    versao: int | None = None,
    chave: str | None = None,
) -> tuple[int, bool]:
    """Cria (sem `transacao_id`) ou edita (com a `versao` lida). Devolve (id, criou_agora).

    Erros de regra saem como `psycopg.Error` com SQLSTATE AB*** (ver `backend.erros_banco`).
    """
    cur = await conn.execute(
        "SELECT transacao_id, criado FROM lancamento_gravar("
        "%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (
            user_id,
            transacao_id,
            versao,
            dados.tipo,
            dados.data,
            dados.valor,
            dados.conta_id,
            dados.conta_destino_id,
            dados.bruto,
            dados.imposto,
            dados.descricao,
            chave,
            hash_corpo(dados) if chave is not None else None,
            dados.parcelas,
            dados.pessoa_id,
        ),
    )
    linha = await cur.fetchone()
    if linha is None:
        raise RuntimeError("lancamento_gravar não devolveu linha")
    return int(linha[0]), bool(linha[1])


async def estornar(
    conn: psycopg.AsyncConnection,
    user_id: int,
    transacao_id: int,
    versao: int,
    data: date,
    descricao: str | None,
) -> EstornoGravado:
    """Estorna a compra inteira. T, P e N saem da função do banco (ADR 044); erros: AB***."""
    cur = await conn.execute(
        "SELECT estorno_id, competencia_credito, total, credito, limite_devolvido "
        "FROM estorno_gravar(%s, %s, %s, %s, %s)",
        (user_id, transacao_id, versao, data, descricao),
    )
    linha = await cur.fetchone()
    if linha is None:
        raise RuntimeError("estorno_gravar não devolveu linha")
    return EstornoGravado(*linha)


async def excluir(
    conn: psycopg.AsyncConnection, user_id: int, transacao_id: int, versao: int
) -> None:
    await conn.execute("SELECT lancamento_excluir(%s, %s, %s)", (user_id, transacao_id, versao))
