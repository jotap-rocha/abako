"""Saldos, snapshots e R4. Fino: valida, delega ao service, formata. Dinheiro sempre texto."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query, status
from pydantic import BaseModel, Field

from backend.deps import Conexao, Sessao, SessaoEscrita
from backend.dinheiro import texto_dinheiro
from backend.services import saldos as svc_saldos
from backend.tipos import TipoConta

router = APIRouter(tags=["saldos"])

# Datas anteriores a isto são erro de digitação; o maior id lógico cabe em bigint.
DATA_MINIMA = date(2000, 1, 1)
IdConta = Annotated[int, Path(ge=1, le=2**63 - 1)]

# Texto decimal com até 2 casas: "1050", "-50.5", "1000.00". Nunca número JSON (INV-14).
PADRAO_VALOR = r"^-?[0-9]{1,12}(\.[0-9]{1,2})?$"


class SaldoSaida(BaseModel):
    conta_id: int
    nome: str
    conta_beneficio: bool
    saldo: str
    snapshot_data: date | None
    snapshot_valor: str | None
    tipo: TipoConta
    # Reserva/investimento que pertence a uma conta corrente (caixinha do banco).
    conta_mae_id: int | None


class SnapshotEntrada(BaseModel):
    data: date = Field(ge=DATA_MINIMA)
    valor: str = Field(pattern=PADRAO_VALOR)


class SnapshotSaida(BaseModel):
    snapshot_id: int
    conta_id: int
    data: date
    valor: str
    # Primeiro snapshot da conta = saldo inicial: âncora, sem comparação (ADR 041).
    saldo_inicial: bool
    # Só vêm preenchidos quando o derivado difere do snapshot (R4). Nada é corrigido.
    saldo_derivado: str | None
    divergencia: str | None


class DivergenciaSaida(BaseModel):
    conta_id: int
    conta_nome: str
    data_snapshot: date
    valor_snapshot: str
    saldo_derivado: str
    divergencia: str


@router.get("/saldos", response_model=list[SaldoSaida])
async def listar(
    conn: Conexao, sessao: Sessao, em: Annotated[date | None, Query(ge=DATA_MINIMA)] = None
) -> list[SaldoSaida]:
    """Saldo derivado de cada conta em `em` (padrão: hoje). Não aceita data futura."""
    hoje = await svc_saldos.hoje(conn)
    if em is not None and em > hoje:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "a data não pode ser futura")
    saldos = await svc_saldos.listar_saldos(conn, sessao.user_id, em or hoje)
    return [
        SaldoSaida(
            conta_id=s.conta_id,
            nome=s.nome,
            conta_beneficio=s.conta_beneficio,
            saldo=texto_dinheiro(s.saldo),
            snapshot_data=s.snapshot_data,
            snapshot_valor=None if s.snapshot_valor is None else texto_dinheiro(s.snapshot_valor),
            tipo=s.tipo,
            conta_mae_id=s.conta_mae_id,
        )
        for s in saldos
    ]


@router.post(
    "/contas/{conta_id}/snapshots",
    response_model=SnapshotSaida,
    status_code=status.HTTP_201_CREATED,
)
async def registrar_snapshot(
    conta_id: IdConta, entrada: SnapshotEntrada, conn: Conexao, sessao: SessaoEscrita
) -> SnapshotSaida:
    """Informa o saldo que o app do banco mostra. A divergência (R4) volta na resposta."""
    if entrada.data > await svc_saldos.hoje(conn):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "a data não pode ser futura")
    registrado = await svc_saldos.registrar_snapshot(
        conn, sessao.user_id, conta_id, entrada.data, Decimal(entrada.valor)
    )
    if registrado is None:
        # 404 também para conta de outro usuário: não revela que existe (INV-13).
        raise HTTPException(status.HTTP_404_NOT_FOUND, "conta não encontrada")
    await conn.commit()  # antes de responder: o front lê o saldo logo em seguida
    return SnapshotSaida(
        snapshot_id=registrado.snapshot_id,
        conta_id=registrado.conta_id,
        data=registrado.data,
        valor=texto_dinheiro(registrado.valor),
        saldo_inicial=registrado.saldo_inicial,
        saldo_derivado=(
            None if registrado.saldo_derivado is None else texto_dinheiro(registrado.saldo_derivado)
        ),
        divergencia=(
            None if registrado.divergencia is None else texto_dinheiro(registrado.divergencia)
        ),
    )


@router.get("/r4", response_model=list[DivergenciaSaida])
async def r4(conn: Conexao, sessao: Sessao) -> list[DivergenciaSaida]:
    """Contas em que o saldo derivado difere do snapshot. Só sinaliza; nunca corrige."""
    divergencias = await svc_saldos.listar_r4(conn, sessao.user_id)
    return [
        DivergenciaSaida(
            conta_id=d.conta_id,
            conta_nome=d.conta_nome,
            data_snapshot=d.data_snapshot,
            valor_snapshot=texto_dinheiro(d.valor_snapshot),
            saldo_derivado=texto_dinheiro(d.saldo_derivado),
            divergencia=texto_dinheiro(d.divergencia),
        )
        for d in divergencias
    ]
