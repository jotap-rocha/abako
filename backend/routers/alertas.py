"""Alertas R1, R2 e R4 (SPEC-011, ADR 049). Fino: delega, formata.

O `user_id` vem sempre da sessão (INV-13); dinheiro sempre texto (INV-14); `hoje` é a data civil de
America/Sao_Paulo, nunca do cliente. O alerta é derivado a cada consulta pela função `alertas` do
banco (sem estado, sem dispensa): código, severidade, mensagem e ordem vêm prontos e o front só
exibe (ADR 015). Valores financeiros nunca vão a log nem a URL.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.deps import Conexao, Sessao
from backend.dinheiro import texto_dinheiro
from backend.services import alertas as svc
from backend.services import gasto_real as svc_data

router = APIRouter(prefix="/alertas", tags=["alertas"])


def hoje_civil() -> date:
    """Dependência (substituível em teste): hoje em America/Sao_Paulo."""
    return svc_data.hoje_civil()


def _texto(valor: Decimal | None) -> str | None:
    return None if valor is None else texto_dinheiro(valor)


class ReservaAlerta(BaseModel):
    # critica | atencao; nulo no item de configuração pendente.
    nivel: str | None
    saldo_liquido: str
    meta: str | None
    falta: str | None
    # Texto com 2 casas.
    cobertura_meses: str | None


class R2Alerta(BaseModel):
    horizonte_dias: int
    data_fim: date
    # Pode ser negativa; só é alerta forte se < 0 (zero não alerta).
    sobra: str
    disponivel: str
    compromissos: str
    # Há cartão com dívida sem vencimento ou fechamento: a sobra não é confiável.
    sobra_nao_confiavel: bool
    vencidas: int
    pendencias_vencimento: int


class R4Alerta(BaseModel):
    conta_id: int
    # O snapshot divergente mais recente (até hoje) e quantos há na conta.
    data_snapshot: date
    valor_snapshot: str
    saldo_derivado: str
    # Derivado menos snapshot (ADR 041); nunca corrigida sozinha.
    divergencia: str
    quantidade: int


class AlertaSaida(BaseModel):
    # R1 | R2 | R4 | CONFIG
    codigo: str
    # alerta (forte) | aviso | configuracao
    tipo: str
    # alta | media | baixa
    severidade: str
    # Identificador estável do caso (reserva_critica, sobra_negativa, divergencia_saldo...).
    detalhe: str
    # Texto literal, sem valores; os números ficam nos blocos abaixo.
    mensagem: str
    reserva: ReservaAlerta | None
    r2: R2Alerta | None
    r4: R4Alerta | None


class AlertasSaida(BaseModel):
    # O `hoje` civil usado na consulta.
    data_referencia: date
    # Já ordenados: severidade (alta, media, baixa), depois código.
    itens: list[AlertaSaida]


def _reserva(a: svc.Alerta) -> ReservaAlerta | None:
    if a.codigo not in ("R1", "CONFIG") or a.saldo_liquido is None:
        return None
    return ReservaAlerta(
        nivel=a.nivel,
        saldo_liquido=texto_dinheiro(a.saldo_liquido),
        meta=_texto(a.meta),
        falta=_texto(a.falta),
        cobertura_meses=_texto(a.cobertura_meses),
    )


def _r2(a: svc.Alerta) -> R2Alerta | None:
    if a.codigo != "R2":
        return None
    if (
        a.horizonte_dias is None
        or a.data_fim is None
        or a.sobra is None
        or a.disponivel is None
        or a.compromissos is None
    ):  # a função do banco sempre preenche o R2: só falta se o banco estiver incoerente
        raise RuntimeError("alerta R2 incompleto")
    return R2Alerta(
        horizonte_dias=a.horizonte_dias,
        data_fim=a.data_fim,
        sobra=texto_dinheiro(a.sobra),
        disponivel=texto_dinheiro(a.disponivel),
        compromissos=texto_dinheiro(a.compromissos),
        sobra_nao_confiavel=bool(a.sobra_nao_confiavel),
        vencidas=a.vencidas or 0,
        pendencias_vencimento=a.pendencias_vencimento or 0,
    )


def _r4(a: svc.Alerta) -> R4Alerta | None:
    if a.codigo != "R4":
        return None
    if (
        a.conta_id is None
        or a.data_snapshot is None
        or a.valor_snapshot is None
        or a.saldo_derivado is None
        or a.divergencia is None
        or a.quantidade is None
    ):  # idem: o banco sempre preenche o R4
        raise RuntimeError("alerta R4 incompleto")
    return R4Alerta(
        conta_id=a.conta_id,
        data_snapshot=a.data_snapshot,
        valor_snapshot=texto_dinheiro(a.valor_snapshot),
        saldo_derivado=texto_dinheiro(a.saldo_derivado),
        divergencia=texto_dinheiro(a.divergencia),
        quantidade=a.quantidade,
    )


def _saida(a: svc.Alerta) -> AlertaSaida:
    return AlertaSaida(
        codigo=a.codigo,
        tipo=a.tipo,
        severidade=a.severidade,
        detalhe=a.detalhe,
        mensagem=a.mensagem,
        reserva=_reserva(a),
        r2=_r2(a),
        r4=_r4(a),
    )


@router.get("", response_model=AlertasSaida)
async def listar(
    conn: Conexao, sessao: Sessao, hoje: Annotated[date, Depends(hoje_civil)]
) -> AlertasSaida:
    """Alertas R1, R2 e R4 em `hoje` (data civil de São Paulo), derivados a cada consulta."""
    itens = await svc.listar(conn, sessao.user_id, hoje)
    return AlertasSaida(data_referencia=hoje, itens=[_saida(a) for a in itens])
