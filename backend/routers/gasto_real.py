"""Gasto real e receita do mês (SPEC-008, ADR 046). Fino: valida, delega, formata.

O `user_id` vem sempre da sessão (INV-13); dinheiro sempre texto (INV-14). Só leitura. A única
coisa na URL é o mês (`AAAA-MM`); mês fora do formato é recusado pelo banco (422/AB422).
"""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from backend.deps import Conexao, Sessao
from backend.dinheiro import texto_dinheiro
from backend.erros_banco import mes_valido, regras_do_banco
from backend.services import gasto_real as svc

router = APIRouter(tags=["gasto_real"])


def hoje_civil() -> date:
    """Dependência (substituível em teste): hoje em America/Sao_Paulo."""
    return svc.hoje_civil()


# Sem `pattern` nem `max_length`: o formato é decidido só pelo banco (mes_inicio), sempre AB422.
MesParam = Annotated[
    str | None,
    Query(description="Mês AAAA-MM; padrão: o mês corrente em America/Sao_Paulo"),
]


def _mes(mes: str | None, hoje: date) -> str:
    return mes_valido(mes) if mes is not None else hoje.strftime("%Y-%m")


class GastoContaSaida(BaseModel):
    conta_id: int
    valor: str


class GastoRealSaida(BaseModel):
    mes: str
    total: str
    por_conta: list[GastoContaSaida]


class ReceitaSaida(BaseModel):
    mes: str
    # Só o tipo receita fora de conta de benefício; a visão principal usa esta.
    caixa: str
    beneficio: str
    # caixa + benefício (INV-24).
    total: str


@router.get("/gasto-real", response_model=GastoRealSaida)
async def gasto_real(
    conn: Conexao,
    sessao: Sessao,
    hoje: Annotated[date, Depends(hoje_civil)],
    mes: MesParam = None,
) -> GastoRealSaida:
    """Gasto real do mês, total e por conta, derivado a cada consulta (ADR 046)."""
    alvo = _mes(mes, hoje)
    async with regras_do_banco():
        resultado = await svc.gasto_real(conn, sessao.user_id, alvo)
    return GastoRealSaida(
        mes=alvo,
        total=texto_dinheiro(resultado.total),
        por_conta=[
            GastoContaSaida(conta_id=g.conta_id, valor=texto_dinheiro(g.valor))
            for g in resultado.por_conta
        ],
    )


@router.get("/receita", response_model=ReceitaSaida)
async def receita(
    conn: Conexao,
    sessao: Sessao,
    hoje: Annotated[date, Depends(hoje_civil)],
    mes: MesParam = None,
) -> ReceitaSaida:
    """Receita de caixa, de benefício e total do mês (ADR 046 item 7)."""
    alvo = _mes(mes, hoje)
    async with regras_do_banco():
        r = await svc.receita(conn, sessao.user_id, alvo)
    return ReceitaSaida(
        mes=alvo,
        caixa=texto_dinheiro(r.caixa),
        beneficio=texto_dinheiro(r.beneficio),
        total=texto_dinheiro(r.total),
    )
