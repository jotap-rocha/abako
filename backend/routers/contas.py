"""Contas do usuário da sessão. Não existe parâmetro de `user_id` (INV-13)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from backend.deps import Conexao, Sessao
from backend.services import contas as svc_contas

router = APIRouter(prefix="/contas", tags=["contas"])


class ContaSaida(BaseModel):
    conta_id: int
    nome: str
    conta_beneficio: bool


@router.get("", response_model=list[ContaSaida])
async def listar(conn: Conexao, sessao: Sessao) -> list[ContaSaida]:
    contas = await svc_contas.listar(conn, sessao.user_id)
    return [ContaSaida(**vars(c)) for c in contas]


@router.get("/{conta_id}", response_model=ContaSaida)
async def obter(conta_id: int, conn: Conexao, sessao: Sessao) -> ContaSaida:
    conta = await svc_contas.obter(conn, sessao.user_id, conta_id)
    if conta is None:
        # 404 também para conta de outro usuário: não revela que existe.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "conta não encontrada")
    return ContaSaida(**vars(conta))
