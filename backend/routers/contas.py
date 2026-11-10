"""Contas do usuário da sessão. Não existe parâmetro de `user_id` (INV-13).

Tipo de conta (ADR 042/043): corrente, reserva, investimento, benefício ou divida (cartão, que
exige `linha_credito_id`). Reserva/investimento pode
pertencer a uma conta corrente do mesmo banco (a caixinha/cofre), com saldo próprio.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, status
from pydantic import BaseModel, Field, field_validator, model_validator

from backend.deps import Conexao, Sessao, SessaoEscrita
from backend.erros_banco import regras_do_banco
from backend.services import contas as svc_contas
from backend.tipos import TipoConta

router = APIRouter(prefix="/contas", tags=["contas"])

IdConta = Annotated[int, Path(ge=1, le=2**63 - 1)]


class ContaSaida(BaseModel):
    conta_id: int
    nome: str
    conta_beneficio: bool
    tipo: TipoConta
    # A conta corrente a que esta reserva/investimento pertence (ex.: caixinha do banco).
    conta_mae_id: int | None
    versao: int
    # A linha de crédito do cartão (só conta do tipo "divida").
    linha_credito_id: int | None = None


class _Nome(BaseModel):
    nome: str = Field(min_length=1, max_length=80)

    @field_validator("nome")
    @classmethod
    def _sem_espacos_nas_pontas(cls, nome: str) -> str:
        limpo = nome.strip()
        if not limpo:
            raise ValueError("o nome não pode ficar vazio")
        return limpo


class ContaEntrada(_Nome):
    # Sem `tipo`, vale o campo antigo: benefício marcado = "beneficio", senão "corrente".
    conta_beneficio: bool = False
    tipo: TipoConta | None = None
    conta_mae_id: Annotated[int, Field(ge=1, le=2**63 - 1)] | None = None
    linha_credito_id: Annotated[int, Field(ge=1, le=2**63 - 1)] | None = None

    @model_validator(mode="after")
    def _tipo_coerente(self) -> ContaEntrada:
        if self.tipo is not None and self.conta_beneficio != (self.tipo == "beneficio"):
            raise ValueError("conta_beneficio e tipo não combinam")
        return self

    def tipo_final(self) -> str:
        if self.tipo is not None:
            return self.tipo
        return "beneficio" if self.conta_beneficio else "corrente"


class ContaEdicao(_Nome):
    tipo: TipoConta
    conta_mae_id: Annotated[int, Field(ge=1, le=2**63 - 1)] | None = None
    linha_credito_id: Annotated[int, Field(ge=1, le=2**63 - 1)] | None = None
    # A versão que o front leu; se outra edição veio antes, 409.
    versao: int = Field(ge=1)


def _saida(conta: svc_contas.Conta) -> ContaSaida:
    return ContaSaida(**vars(conta))


@router.post("", response_model=ContaSaida, status_code=status.HTTP_201_CREATED)
async def criar(entrada: ContaEntrada, conn: Conexao, sessao: SessaoEscrita) -> ContaSaida:
    async with regras_do_banco():
        conta_id = await svc_contas.gravar(
            conn,
            sessao.user_id,
            nome=entrada.nome,
            tipo=entrada.tipo_final(),
            conta_mae_id=entrada.conta_mae_id,
            linha_credito_id=entrada.linha_credito_id,
        )
    conta = await svc_contas.obter(conn, sessao.user_id, conta_id)
    if conta is None:  # a função acabou de gravar: só falta se o banco estiver incoerente
        raise RuntimeError("conta gravada não encontrada")
    await conn.commit()
    return _saida(conta)


@router.get("", response_model=list[ContaSaida])
async def listar(conn: Conexao, sessao: Sessao) -> list[ContaSaida]:
    contas = await svc_contas.listar(conn, sessao.user_id)
    return [_saida(c) for c in contas]


@router.get("/{conta_id}", response_model=ContaSaida)
async def obter(conta_id: IdConta, conn: Conexao, sessao: Sessao) -> ContaSaida:
    conta = await svc_contas.obter(conn, sessao.user_id, conta_id)
    if conta is None:
        # 404 também para conta de outro usuário: não revela que existe.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "conta não encontrada")
    return _saida(conta)


@router.put("/{conta_id}", response_model=ContaSaida)
async def editar(
    conta_id: IdConta, entrada: ContaEdicao, conn: Conexao, sessao: SessaoEscrita
) -> ContaSaida:
    """Nome, tipo e conta do banco. Cria nova versão; a anterior fica no histórico."""
    async with regras_do_banco():
        await svc_contas.gravar(
            conn,
            sessao.user_id,
            nome=entrada.nome,
            tipo=entrada.tipo,
            conta_mae_id=entrada.conta_mae_id,
            linha_credito_id=entrada.linha_credito_id,
            conta_id=conta_id,
            versao=entrada.versao,
        )
    conta = await svc_contas.obter(conn, sessao.user_id, conta_id)
    if conta is None:  # a função acabou de gravar: só falta se o banco estiver incoerente
        raise RuntimeError("conta gravada não encontrada")
    await conn.commit()
    return _saida(conta)
