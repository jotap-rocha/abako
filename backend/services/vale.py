"""Vale (VR) com bolsos, sobra com decisão e benefícios (SPEC-013, ADR 052).

Toda a regra (alocação por bolso, ajuste encadeado, sobra, estado, receita total) vive nas funções
da migração 0013; aqui só se monta a chamada, sempre com o `user_id` da sessão (INV-13). Nenhum
cálculo financeiro em Python. Valores nunca vão a log.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import psycopg

COLUNAS_SITUACAO = (
    "mes, mes_encerrado, estado, conta_vr_id, credito, base_trabalho, "
    "inicial_trabalho, inicial_pessoal, ajuste_trabalho, ajuste_pessoal, "
    "alocacao_trabalho, alocacao_pessoal, consumo_trabalho, consumo_pessoal, "
    "resta_trabalho, resta_pessoal, sobra, decisao_destino, decisao_versao, destino_padrao, "
    "saldo_total, receita_caixa, receita_beneficio, receita_total"
)


@dataclass(frozen=True)
class Situacao:
    mes: str
    mes_encerrado: bool
    estado: str
    conta_vr_id: int | None
    credito: Decimal
    base_trabalho: Decimal | None
    inicial_trabalho: Decimal
    inicial_pessoal: Decimal
    ajuste_trabalho: Decimal
    ajuste_pessoal: Decimal
    alocacao_trabalho: Decimal
    alocacao_pessoal: Decimal
    consumo_trabalho: Decimal
    consumo_pessoal: Decimal
    resta_trabalho: Decimal
    resta_pessoal: Decimal
    sobra: Decimal
    decisao_destino: str | None
    decisao_versao: int | None
    destino_padrao: str
    saldo_total: Decimal | None
    receita_caixa: Decimal
    receita_beneficio: Decimal
    receita_total: Decimal


@dataclass(frozen=True)
class Beneficio:
    conta_id: int
    vale_refeicao: bool
    receita_mes: Decimal
    despesa_mes: Decimal
    saldo_total: Decimal


@dataclass(frozen=True)
class Parametro:
    conta_id: int
    base_trabalho: Decimal
    destino_padrao: str
    vigente_desde: date


@dataclass(frozen=True)
class Decisao:
    mes: date
    destino: str
    versao: int
    vigente: bool


async def situacao(conn: psycopg.AsyncConnection, user_id: int, mes: str, hoje: date) -> Situacao:
    """Mês inválido: o banco recusa com AB422 (traduzido pelo router)."""
    cur = await conn.execute(
        f"SELECT {COLUNAS_SITUACAO} FROM vale_situacao(%s, %s, %s)",  # noqa: S608
        (user_id, mes, hoje),
    )
    linha = await cur.fetchone()
    if linha is None:
        raise RuntimeError("vale_situacao não devolveu linha")
    return Situacao(*linha)


async def beneficios(
    conn: psycopg.AsyncConnection, user_id: int, mes: str, hoje: date
) -> list[Beneficio]:
    cur = await conn.execute(
        "SELECT conta_id, vale_refeicao, receita_mes, despesa_mes, saldo_total "
        "FROM beneficios_contas(%s, %s, %s)",
        (user_id, mes, hoje),
    )
    return [Beneficio(*r) for r in await cur.fetchall()]


async def parametro_vigente_em(
    conn: psycopg.AsyncConnection, user_id: int, mes: str
) -> Parametro | None:
    """O parâmetro de maior vigência menor ou igual ao mês (mesma escolha das funções)."""
    cur = await conn.execute(
        "SELECT conta_id, base_trabalho, destino_padrao, vigente_desde "
        "FROM vale_parametro_vigente WHERE user_id = %s AND vigente_desde <= mes_inicio(%s) "
        "ORDER BY vigente_desde DESC LIMIT 1",
        (user_id, mes),
    )
    linha = await cur.fetchone()
    return None if linha is None else Parametro(*linha)


async def gravar_parametro(
    conn: psycopg.AsyncConnection,
    user_id: int,
    conta_id: int,
    base_trabalho: Decimal,
    destino_padrao: str,
    vigente_desde: date,
) -> Parametro:
    """Valores inválidos: o banco recusa com AB404/AB422 (traduzido pelo router)."""
    cur = await conn.execute(
        "SELECT vale_parametro_gravar(%s, %s, %s, %s, %s)",
        (user_id, conta_id, base_trabalho, destino_padrao, vigente_desde),
    )
    linha = await cur.fetchone()
    if linha is None:
        raise RuntimeError("vale_parametro_gravar não devolveu linha")
    cur = await conn.execute(
        "SELECT conta_id, base_trabalho, destino_padrao, vigente_desde "
        "FROM vale_parametro WHERE user_id = %s AND id = %s",
        (user_id, linha[0]),
    )
    gravado = await cur.fetchone()
    if gravado is None:  # a função acabou de gravar: só falta se o banco estiver incoerente
        raise RuntimeError("parâmetro do vale gravado não encontrado")
    return Parametro(*gravado)


async def gravar_decisao(
    conn: psycopg.AsyncConnection, user_id: int, mes: str, destino: str
) -> int:
    """Devolve a versão vigente da decisão do mês; erros de regra: AB422 (traduzido no router)."""
    cur = await conn.execute("SELECT vale_decisao_gravar(%s, %s, %s)", (user_id, mes, destino))
    linha = await cur.fetchone()
    if linha is None:
        raise RuntimeError("vale_decisao_gravar não devolveu linha")
    return int(linha[0])


async def listar_decisoes(
    conn: psycopg.AsyncConnection, user_id: int, mes: str | None
) -> list[Decisao]:
    """Histórico (todas as versões) por mês; `vigente` marca a maior versão de cada mês."""
    sql = (
        "SELECT d.mes, d.destino, d.versao, "
        "d.versao = max(d.versao) OVER (PARTITION BY d.user_id, d.mes) "
        "FROM vale_decisao d WHERE d.user_id = %s"
    )
    params: list[object] = [user_id]
    if mes is not None:
        sql += " AND d.mes = mes_inicio(%s)"
        params.append(mes)
    sql += " ORDER BY d.mes, d.versao"
    cur = await conn.execute(sql, params)
    return [Decisao(*r) for r in await cur.fetchall()]
