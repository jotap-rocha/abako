"""Linhas de crédito, fechamento e fatura do cartão (SPEC-005, ADR 043). Fino: valida, delega,
formata. O `user_id` vem sempre da sessão (INV-13); dinheiro sempre texto (INV-14)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query, status
from pydantic import BaseModel, Field, field_validator

from backend.deps import Conexao, Sessao, SessaoEscrita
from backend.dinheiro import texto_dinheiro
from backend.erros_banco import regras_do_banco
from backend.routers.saldos import DATA_MINIMA
from backend.services import cartoes as svc

router_linhas = APIRouter(prefix="/linhas-credito", tags=["linhas_credito"])
router_cartoes = APIRouter(prefix="/cartoes", tags=["cartoes"])

IdLinha = Annotated[int, Path(ge=1, le=2**63 - 1)]
IdConta = Annotated[int, Path(ge=1, le=2**63 - 1)]
Competencia = Annotated[str, Path(pattern=r"^[0-9]{4}-(0[1-9]|1[0-2])$")]
PADRAO_LIMITE = r"^[0-9]{1,12}(\.[0-9]{1,2})?$"


# ------------------------------------------------------------------ linha de crédito


class LinhaEntrada(BaseModel):
    nome: str = Field(min_length=1, max_length=80)
    limite: str = Field(pattern=PADRAO_LIMITE)

    @field_validator("nome")
    @classmethod
    def _sem_espacos_nas_pontas(cls, nome: str) -> str:
        limpo = nome.strip()
        if not limpo:
            raise ValueError("o nome não pode ficar vazio")
        return limpo


class LinhaEdicao(LinhaEntrada):
    # A versão que o front leu; se outra edição veio antes, 409.
    versao: int = Field(ge=1)


class LinhaSaida(BaseModel):
    linha_id: int
    nome: str
    limite: str
    versao: int


class LimiteSaida(BaseModel):
    limite: str
    usado: str
    # Pode ser negativo: nada bloqueia a compra (ADR 043).
    disponivel: str


def _saida_linha(linha: svc.Linha) -> LinhaSaida:
    return LinhaSaida(
        linha_id=linha.linha_id,
        nome=linha.nome,
        limite=texto_dinheiro(linha.limite),
        versao=linha.versao,
    )


async def _linha_gravada(conn: Conexao, user_id: int, linha_id: int) -> LinhaSaida:
    linha = await svc.obter_linha(conn, user_id, linha_id)
    if linha is None:  # a função acabou de gravar: só falta se o banco estiver incoerente
        raise RuntimeError("linha gravada não encontrada")
    await conn.commit()
    return _saida_linha(linha)


@router_linhas.post("", response_model=LinhaSaida, status_code=status.HTTP_201_CREATED)
async def criar(entrada: LinhaEntrada, conn: Conexao, sessao: SessaoEscrita) -> LinhaSaida:
    async with regras_do_banco():
        linha_id = await svc.gravar_linha(
            conn, sessao.user_id, nome=entrada.nome, limite=Decimal(entrada.limite)
        )
    return await _linha_gravada(conn, sessao.user_id, linha_id)


@router_linhas.get("", response_model=list[LinhaSaida])
async def listar(conn: Conexao, sessao: Sessao) -> list[LinhaSaida]:
    return [_saida_linha(linha) for linha in await svc.listar_linhas(conn, sessao.user_id)]


@router_linhas.put("/{linha_id}", response_model=LinhaSaida)
async def editar(
    linha_id: IdLinha, entrada: LinhaEdicao, conn: Conexao, sessao: SessaoEscrita
) -> LinhaSaida:
    """Nome e limite. Cria nova versão; a anterior fica no histórico."""
    async with regras_do_banco():
        await svc.gravar_linha(
            conn,
            sessao.user_id,
            nome=entrada.nome,
            limite=Decimal(entrada.limite),
            linha_id=linha_id,
            versao=entrada.versao,
        )
    return await _linha_gravada(conn, sessao.user_id, linha_id)


@router_linhas.get("/{linha_id}/limite", response_model=LimiteSaida)
async def limite(
    linha_id: IdLinha,
    conn: Conexao,
    sessao: Sessao,
    em: Annotated[date | None, Query(ge=DATA_MINIMA)] = None,
) -> LimiteSaida:
    """Limite, usado (dívida das compras ainda não pagas, com parcelas futuras) e disponível."""
    resultado = await svc.limite_da_linha(conn, sessao.user_id, linha_id, em)
    if resultado is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "linha de crédito não encontrada")
    return LimiteSaida(
        limite=texto_dinheiro(resultado.limite),
        usado=texto_dinheiro(resultado.usado),
        disponivel=texto_dinheiro(resultado.disponivel),
    )


# ------------------------------------------------------------------ fechamento e fatura


class FechamentoEntrada(BaseModel):
    dia: int = Field(ge=1, le=31)
    vigente_desde: date = Field(ge=DATA_MINIMA)


class FechamentoSaida(BaseModel):
    dia: int
    vigente_desde: date


class ItemFaturaSaida(BaseModel):
    transacao_id: int
    versao: int
    parcela: int
    parcelas: int
    data_compra: date
    valor: str
    descricao: str | None
    # Nula = própria. O nome da pessoa vem de /pessoas (nunca na fatura).
    pessoa_id: int | None


class FaturaSaida(BaseModel):
    competencia: str
    # total = propria + terceiros. Terceiros entra na fatura e no limite, não no gasto real.
    total: str
    propria: str
    terceiros: str
    itens: list[ItemFaturaSaida]


async def _exigir_cartao(conn: Conexao, user_id: int, conta_id: int) -> None:
    """404 também para o cartão de outro usuário: não revela que existe."""
    if not await svc.eh_cartao(conn, user_id, conta_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "cartão não encontrado")


@router_cartoes.post(
    "/{conta_id}/fechamentos", response_model=FechamentoSaida, status_code=status.HTTP_201_CREATED
)
async def registrar_fechamento(
    conta_id: IdConta, entrada: FechamentoEntrada, conn: Conexao, sessao: SessaoEscrita
) -> FechamentoSaida:
    """Dia de fechamento a partir de uma data; não recalcula compras já feitas (ADR 043)."""
    async with regras_do_banco():
        await svc.gravar_fechamento(
            conn, sessao.user_id, conta_id, entrada.dia, entrada.vigente_desde
        )
    await conn.commit()
    return FechamentoSaida(dia=entrada.dia, vigente_desde=entrada.vigente_desde)


@router_cartoes.get("/{conta_id}/fechamentos", response_model=list[FechamentoSaida])
async def listar_fechamentos(
    conta_id: IdConta, conn: Conexao, sessao: Sessao
) -> list[FechamentoSaida]:
    await _exigir_cartao(conn, sessao.user_id, conta_id)
    lista = await svc.listar_fechamentos(conn, sessao.user_id, conta_id)
    return [FechamentoSaida(dia=f.dia, vigente_desde=f.vigente_desde) for f in lista]


@router_cartoes.get("/{conta_id}/faturas/{competencia}", response_model=FaturaSaida)
async def fatura(
    conta_id: IdConta, competencia: Competencia, conn: Conexao, sessao: Sessao
) -> FaturaSaida:
    """Parcelas da competência (mês do fechamento, "YYYY-MM"), total, própria e terceiros."""
    await _exigir_cartao(conn, sessao.user_id, conta_id)
    itens = await svc.itens_da_fatura(conn, sessao.user_id, conta_id, competencia)
    resumo = await svc.resumo_da_fatura(conn, sessao.user_id, conta_id, competencia)
    return FaturaSaida(
        competencia=competencia,
        total=texto_dinheiro(resumo.total),
        propria=texto_dinheiro(resumo.propria),
        terceiros=texto_dinheiro(resumo.terceiros),
        itens=[
            ItemFaturaSaida(
                transacao_id=i.transacao_id,
                versao=i.versao,
                parcela=i.parcela,
                parcelas=i.parcelas,
                data_compra=i.data_compra,
                valor=texto_dinheiro(i.valor),
                descricao=i.descricao,
                pessoa_id=i.pessoa_id,
            )
            for i in itens
        ],
    )
