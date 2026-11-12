"""Situação do R2, horizonte e vencimento do cartão (SPEC-010, ADR 048). Fino: valida, delega,
formata.

O `user_id` vem sempre da sessão (INV-13); dinheiro sempre texto (INV-14); `hoje` é a data civil de
America/Sao_Paulo, nunca do cliente. Disponível, compromissos, sobra e alerta são decididos pelo
banco; o front só exibe (ADR 015). Valores financeiros nunca vão a log nem a URL.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path, status
from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.deps import Conexao, Sessao, SessaoEscrita
from backend.dinheiro import texto_dinheiro
from backend.erros_banco import regras_do_banco
from backend.services import cartoes as svc_cartoes
from backend.services import gasto_real as svc_data
from backend.services import r2 as svc

router = APIRouter(prefix="/r2", tags=["r2"])
router_vencimentos = APIRouter(prefix="/cartoes", tags=["vencimentos"])

IdConta = Annotated[int, Path(ge=1, le=2**63 - 1)]


def hoje_civil() -> date:
    """Dependência (substituível em teste): hoje em America/Sao_Paulo."""
    return svc_data.hoje_civil()


def _texto(valor: Decimal | None) -> str | None:
    return None if valor is None else texto_dinheiro(valor)


class _CorpoSemUserId(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def _sem_user_id(cls, corpo: Any) -> Any:
        """`user_id` no corpo é descartado: a sessão manda (INV-13). Outra chave é 422."""
        if isinstance(corpo, dict):
            return {k: v for k, v in corpo.items() if k != "user_id"}
        return corpo


# ------------------------------------------------------------------ horizonte


class HorizonteEntrada(_CorpoSemUserId):
    # 1 a 90 e datas desde 2000 são do banco (AB422); aqui só o que evita estouro de tipo (500).
    dias: int = Field(ge=-(2**31), le=2**31 - 1)
    vigente_desde: date


class HorizonteSaida(BaseModel):
    dias: int
    vigente_desde: date


@router.get("/horizonte", response_model=list[HorizonteSaida])
async def listar_horizontes(conn: Conexao, sessao: Sessao) -> list[HorizonteSaida]:
    """Um horizonte por `vigente_desde` (o último gravado), do mais antigo ao mais novo."""
    return [
        HorizonteSaida(dias=h.dias, vigente_desde=h.vigente_desde)
        for h in await svc.listar_horizontes(conn, sessao.user_id)
    ]


@router.put("/horizonte", response_model=HorizonteSaida, status_code=status.HTTP_200_OK)
async def gravar_horizonte(
    entrada: HorizonteEntrada, conn: Conexao, sessao: SessaoEscrita
) -> HorizonteSaida:
    """Grava o horizonte a partir de `vigente_desde`; repetir é idempotente."""
    async with regras_do_banco():
        await svc.gravar_horizonte(conn, sessao.user_id, entrada.dias, entrada.vigente_desde)
    gravado = await svc.obter_horizonte(conn, sessao.user_id, entrada.vigente_desde)
    if gravado is None:  # a função acabou de gravar: só falta se o banco estiver incoerente
        raise RuntimeError("horizonte gravado não encontrado")
    await conn.commit()
    return HorizonteSaida(dias=gravado.dias, vigente_desde=gravado.vigente_desde)


# ------------------------------------------------------------------ situação


class ItemR2Saida(BaseModel):
    # receita | fixo | fatura | vencida (a vencida fica fora da sobra, INV-19).
    grupo: str
    # fixo | receita nos itens de recorrente; nulo na fatura.
    tipo: str | None
    recorrente_id: int | None
    conta_id: int
    # AAAA-MM, só na fatura.
    competencia: str | None
    data: date
    valor: str
    # Só na fatura: própria bruta, pago alocado e se ainda está aberta.
    bruto: str | None
    pago: str | None
    parcial: bool | None


class SituacaoR2Saida(BaseModel):
    horizonte_dias: int
    data_fim: date
    saldos_correntes: str
    receitas_pendentes: str
    disponivel: str
    fixos_pendentes: str
    faturas_proprias: str
    compromissos: str
    # Pode ser negativa; alerta = sobra < 0 (a tela do alerta é da task 17).
    sobra: str
    alerta: bool
    # Quantidade de ocorrências vencidas e não vinculadas (lista à parte, fora da sobra).
    vencidas: int
    # Cartões com dívida e sem vencimento cadastrado (ficam fora da sobra).
    pendencias_vencimento: int
    itens: list[ItemR2Saida]


@router.get("", response_model=SituacaoR2Saida)
async def situacao(
    conn: Conexao, sessao: Sessao, hoje: Annotated[date, Depends(hoje_civil)]
) -> SituacaoR2Saida:
    """Sobra do R2 em `hoje` (data civil de São Paulo), derivada a cada consulta (ADR 048)."""
    s, itens = await svc.situacao_com_itens(conn, sessao.user_id, hoje)
    return SituacaoR2Saida(
        horizonte_dias=s.horizonte_dias,
        data_fim=s.data_fim,
        saldos_correntes=texto_dinheiro(s.saldos_correntes),
        receitas_pendentes=texto_dinheiro(s.receitas_pendentes),
        disponivel=texto_dinheiro(s.disponivel),
        fixos_pendentes=texto_dinheiro(s.fixos_pendentes),
        faturas_proprias=texto_dinheiro(s.faturas_proprias),
        compromissos=texto_dinheiro(s.compromissos),
        sobra=texto_dinheiro(s.sobra),
        alerta=s.alerta,
        vencidas=s.vencidas,
        pendencias_vencimento=s.pendencias_vencimento,
        itens=[
            ItemR2Saida(
                grupo=i.grupo,
                tipo=i.tipo,
                recorrente_id=i.recorrente_id,
                conta_id=i.conta_id,
                competencia=i.competencia,
                data=i.data,
                valor=texto_dinheiro(i.valor),
                bruto=_texto(i.bruto),
                pago=_texto(i.pago),
                parcial=i.parcial,
            )
            for i in itens
        ],
    )


# ------------------------------------------------------------------ vencimento do cartão


class VencimentoEntrada(_CorpoSemUserId):
    # 1 a 31 e datas desde 2000 são do banco (AB422).
    dia: int = Field(ge=-(2**31), le=2**31 - 1)
    vigente_desde: date


class VencimentoSaida(BaseModel):
    dia: int
    vigente_desde: date


async def _exigir_cartao(conn: Conexao, user_id: int, conta_id: int) -> None:
    """404 também para o cartão de outro usuário: não revela que existe."""
    if not await svc_cartoes.eh_cartao(conn, user_id, conta_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "cartão não encontrado")


@router_vencimentos.get("/{conta_id}/vencimentos", response_model=list[VencimentoSaida])
async def listar_vencimentos(
    conta_id: IdConta, conn: Conexao, sessao: Sessao
) -> list[VencimentoSaida]:
    await _exigir_cartao(conn, sessao.user_id, conta_id)
    lista = await svc.listar_vencimentos(conn, sessao.user_id, conta_id)
    return [VencimentoSaida(dia=v.dia, vigente_desde=v.vigente_desde) for v in lista]


@router_vencimentos.put("/{conta_id}/vencimentos", response_model=VencimentoSaida)
async def gravar_vencimento(
    conta_id: IdConta, entrada: VencimentoEntrada, conn: Conexao, sessao: SessaoEscrita
) -> VencimentoSaida:
    """Dia de vencimento a partir de uma data; repetir é idempotente (ADR 048 item 5)."""
    async with regras_do_banco():
        await svc.gravar_vencimento(
            conn, sessao.user_id, conta_id, entrada.dia, entrada.vigente_desde
        )
    await conn.commit()
    return VencimentoSaida(dia=entrada.dia, vigente_desde=entrada.vigente_desde)
