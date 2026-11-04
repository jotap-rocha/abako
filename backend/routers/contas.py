"""Contas do usuário da sessão. Não existe parâmetro de `user_id` (INV-13)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, status
from pydantic import BaseModel, Field, field_validator

from backend.deps import Conexao, Sessao, SessaoEscrita
from backend.services import contas as svc_contas

router = APIRouter(prefix="/contas", tags=["contas"])


class ContaSaida(BaseModel):
    conta_id: int
    nome: str
    conta_beneficio: bool


class ContaEntrada(BaseModel):
    nome: str = Field(min_length=1, max_length=80)
    conta_beneficio: bool = False

    @field_validator("nome")
    @classmethod
    def _sem_espacos_nas_pontas(cls, nome: str) -> str:
        limpo = nome.strip()
        if not limpo:
            raise ValueError("o nome não pode ficar vazio")
        return limpo


@router.post("", response_model=ContaSaida, status_code=status.HTTP_201_CREATED)
async def criar(entrada: ContaEntrada, conn: Conexao, sessao: SessaoEscrita) -> ContaSaida:
    conta = await svc_contas.criar_conta(
        conn, sessao.user_id, entrada.nome, entrada.conta_beneficio
    )
    if conta is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "já existe uma conta com esse nome")
    await conn.commit()
    return ContaSaida(**vars(conta))


@router.get("", response_model=list[ContaSaida])
async def listar(conn: Conexao, sessao: Sessao) -> list[ContaSaida]:
    contas = await svc_contas.listar(conn, sessao.user_id)
    return [ContaSaida(**vars(c)) for c in contas]


@router.get("/{conta_id}", response_model=ContaSaida)
async def obter(
    conta_id: Annotated[int, Path(ge=1, le=2**63 - 1)], conn: Conexao, sessao: Sessao
) -> ContaSaida:
    conta = await svc_contas.obter(conn, sessao.user_id, conta_id)
    if conta is None:
        # 404 também para conta de outro usuário: não revela que existe.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "conta não encontrada")
    return ContaSaida(**vars(conta))
