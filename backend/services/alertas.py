"""Alertas R1, R2, R4 e R5 (SPEC-011 e SPEC-013, ADR 049 e 052).

Quem decide o que é alerta, a severidade e a ordem é a função `alertas` (migrações 0012 e 0013),
que compõe `reserva_situacao`, `r2_situacao`, `r4_divergencias` e `vale_calculo`; aqui só se monta
a chamada, sempre com o `user_id` da sessão (INV-13) e `hoje` = data civil de America/Sao_Paulo.
Nenhuma regra em Python.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import psycopg
from psycopg import IsolationLevel

COLUNAS = (
    "codigo, tipo, severidade, detalhe, mensagem, nivel, saldo_liquido, meta, falta, "
    "cobertura_meses, horizonte_dias, data_fim, sobra, disponivel, compromissos, "
    "sobra_nao_confiavel, vencidas, pendencias_vencimento, conta_id, data_snapshot, "
    "valor_snapshot, saldo_derivado, divergencia, quantidade, bolso, alocacao, consumo, resta, mes"
)


@dataclass(frozen=True)
class Alerta:
    codigo: str
    tipo: str
    severidade: str
    detalhe: str
    mensagem: str
    # R1 e configuração da reserva
    nivel: str | None
    saldo_liquido: Decimal | None
    meta: Decimal | None
    falta: Decimal | None
    cobertura_meses: Decimal | None
    # R2
    horizonte_dias: int | None
    data_fim: date | None
    sobra: Decimal | None
    disponivel: Decimal | None
    compromissos: Decimal | None
    sobra_nao_confiavel: bool | None
    vencidas: int | None
    pendencias_vencimento: int | None
    # R4
    conta_id: int | None
    data_snapshot: date | None
    valor_snapshot: Decimal | None
    saldo_derivado: Decimal | None
    divergencia: Decimal | None
    quantidade: int | None
    # R5 (vale): o bolso estourado e os números do mês corrente (conta_id é o VR)
    bolso: str | None
    alocacao: Decimal | None
    consumo: Decimal | None
    resta: Decimal | None
    mes: str | None


async def listar(conn: psycopg.AsyncConnection, user_id: int, hoje: date) -> list[Alerta]:
    """Uma transação REPEATABLE READ somente leitura, como em `GET /api/r2`: as três origens do
    alerta vêm do mesmo instante, mesmo sob escrita concorrente."""
    await conn.commit()  # fecha a transação aberta pela sessão; o nível só muda fora de uma
    await conn.set_isolation_level(IsolationLevel.REPEATABLE_READ)
    await conn.set_read_only(True)
    try:
        cur = await conn.execute(
            f"SELECT {COLUNAS} FROM alertas(%s, %s)",  # noqa: S608
            (user_id, hoje),
        )
        linhas = await cur.fetchall()
        await conn.commit()
    except BaseException:
        await conn.rollback()
        raise
    finally:
        await conn.set_read_only(None)
        await conn.set_isolation_level(None)
    return [Alerta(*linha) for linha in linhas]
