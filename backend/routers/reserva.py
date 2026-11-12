"""Reserva: situação, cobertura, aporte e parâmetros (SPEC-009, ADR 047). Fino: valida, delega,
formata.

O `user_id` vem sempre da sessão (INV-13); dinheiro sempre texto (INV-14). Nível, cobertura e
aporte são decididos pelo banco; o front só exibe (ADR 015). Campos que o banco devolve NULL
ficam nulos. Valores financeiros nunca vão a log nem a URL.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.deps import Conexao, Sessao, SessaoEscrita
from backend.dinheiro import texto_dinheiro
from backend.erros_banco import regras_do_banco
from backend.services import gasto_real as svc_data
from backend.services import reserva as svc

router = APIRouter(prefix="/reserva", tags=["reserva"])

# Até 2 casas; zero é aceito (vira configuração pendente). O teto de 1 bilhão é do banco.
PADRAO_GASTO = r"^[0-9]{1,12}(\.[0-9]{1,2})?$"


def hoje_civil() -> date:
    """Dependência (substituível em teste): hoje em America/Sao_Paulo."""
    return svc_data.hoje_civil()


def _texto(valor: Decimal | None) -> str | None:
    return None if valor is None else texto_dinheiro(valor)


class SituacaoSaida(BaseModel):
    contas_reserva: int
    # Líquido: o que o banco credita; cobertura e nível usam este (INV-37).
    saldo_liquido: str
    imposto_acumulado: str
    # Bruto = líquido + imposto acumulado (ADR 034).
    saldo_bruto: str
    meses_meta: int
    # Nulos quando a configuração está pendente (gasto essencial ausente ou zero).
    gasto_essencial: str | None
    meta: str | None
    # critica | atencao | saudavel
    nivel: str | None
    falta: str | None
    # Texto com 2 casas.
    cobertura_meses: str | None
    data_alvo: date | None
    meses_ate_alvo: int | None
    alvo_vencida: bool
    aporte_mensal: str | None
    config_pendente: bool


class ParametroEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Os limites de negócio (N de 1 a 120, gasto abaixo de 1 bilhão, datas desde 2000) são do
    # banco (AB422 -> 422 com X-Abako-Erro); aqui só o que evita estouro de tipo (500).
    meses: int = Field(ge=-(2**31), le=2**31 - 1)
    gasto_essencial: str = Field(pattern=PADRAO_GASTO)
    data_alvo: date | None = None
    vigente_desde: date

    @model_validator(mode="before")
    @classmethod
    def _sem_user_id(cls, corpo: Any) -> Any:
        """`user_id` no corpo é descartado: a sessão manda (INV-13). Outra chave é 422."""
        if isinstance(corpo, dict):
            return {k: v for k, v in corpo.items() if k != "user_id"}
        return corpo


class ParametroSaida(BaseModel):
    vigente_desde: date
    meses: int
    gasto_essencial: str
    data_alvo: date | None


def _saida_parametro(p: svc.Parametro) -> ParametroSaida:
    return ParametroSaida(
        vigente_desde=p.vigente_desde,
        meses=p.meses,
        gasto_essencial=texto_dinheiro(p.gasto_essencial),
        data_alvo=p.data_alvo,
    )


@router.get("", response_model=SituacaoSaida)
async def situacao(
    conn: Conexao, sessao: Sessao, hoje: Annotated[date, Depends(hoje_civil)]
) -> SituacaoSaida:
    """Situação da reserva em `hoje` (data civil de São Paulo), derivada a cada consulta."""
    s = await svc.situacao(conn, sessao.user_id, hoje)
    return SituacaoSaida(
        contas_reserva=s.contas_reserva,
        saldo_liquido=texto_dinheiro(s.saldo_liquido),
        imposto_acumulado=texto_dinheiro(s.imposto_acumulado),
        saldo_bruto=texto_dinheiro(s.saldo_bruto),
        meses_meta=s.meses_meta,
        gasto_essencial=_texto(s.gasto_essencial),
        meta=_texto(s.meta),
        nivel=s.nivel,
        falta=_texto(s.falta),
        cobertura_meses=_texto(s.cobertura_meses),
        data_alvo=s.data_alvo,
        meses_ate_alvo=s.meses_ate_alvo,
        alvo_vencida=s.alvo_vencida,
        aporte_mensal=_texto(s.aporte_mensal),
        config_pendente=s.config_pendente,
    )


@router.get("/parametros", response_model=list[ParametroSaida])
async def listar_parametros(conn: Conexao, sessao: Sessao) -> list[ParametroSaida]:
    """Um parâmetro por `vigente_desde` (o último gravado), do mais antigo ao mais novo."""
    return [_saida_parametro(p) for p in await svc.listar_parametros(conn, sessao.user_id)]


@router.put("/parametros", response_model=ParametroSaida, status_code=status.HTTP_200_OK)
async def gravar_parametros(
    entrada: ParametroEntrada, conn: Conexao, sessao: SessaoEscrita
) -> ParametroSaida:
    """Grava os três valores juntos a partir de `vigente_desde`; repetir é idempotente."""
    async with regras_do_banco():
        await svc.gravar_parametro(
            conn,
            sessao.user_id,
            entrada.meses,
            Decimal(entrada.gasto_essencial),
            entrada.data_alvo,
            entrada.vigente_desde,
        )
    gravado = await svc.obter_parametro(conn, sessao.user_id, entrada.vigente_desde)
    if gravado is None:  # a função acabou de gravar: só falta se o banco estiver incoerente
        raise RuntimeError("parâmetro gravado não encontrado")
    await conn.commit()
    return _saida_parametro(gravado)
