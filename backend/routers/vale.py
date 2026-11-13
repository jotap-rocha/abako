"""Vale (VR): situação do mês, benefícios, parâmetro e decisão da sobra (SPEC-013, ADR 052).
Fino: valida, delega, formata.

O `user_id` vem sempre da sessão (INV-13); dinheiro sempre texto (INV-14); `hoje` é a data civil de
America/Sao_Paulo, nunca do cliente. Alocação, ajuste, resta, sobra e estado são decididos pelo
banco; o front só exibe (ADR 015). A única coisa na URL é o mês (`AAAA-MM`). Valores financeiros
nunca vão a log nem a URL. A tela principal nunca consulta estas rotas.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.deps import Conexao, Sessao, SessaoEscrita
from backend.dinheiro import texto_dinheiro
from backend.erros_banco import mes_valido, regras_do_banco
from backend.services import gasto_real as svc_data
from backend.services import vale as svc

router = APIRouter(prefix="/vale", tags=["vale"])

PADRAO_BASE = r"^[0-9]{1,12}(\.[0-9]{1,2})?$"
IdConta = Annotated[int, Field(ge=1, le=2**63 - 1)]
# Sem `pattern`/`max_length`: o formato é decidido só pelo banco (mes_inicio), sempre AB422.
MesParam = Annotated[
    str | None,
    Query(description="Mês AAAA-MM; padrão: o mês corrente em America/Sao_Paulo"),
]


def hoje_civil() -> date:
    """Dependência (substituível em teste): hoje em America/Sao_Paulo."""
    return svc_data.hoje_civil()


def _mes(mes: str | None, hoje: date) -> str:
    return mes_valido(mes) if mes is not None else hoje.strftime("%Y-%m")


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


def _texto_limpo(valor: str) -> str:
    """Texto curto sem caractere de controle (NUL daria 500 no driver)."""
    if len(valor) > 16 or any(not c.isprintable() for c in valor):
        raise ValueError("valor inválido")
    return valor


# ------------------------------------------------------------------ situação do mês


class BolsoSaida(BaseModel):
    # Alocação inicial (mín./máx. com a base), ajuste (sobra decidida do mês anterior), alocação
    # efetiva, consumo e resta (pode ser negativo). Tudo calculado pelo banco.
    inicial: str
    ajuste: str
    alocacao: str
    consumo: str
    resta: str


class SituacaoValeSaida(BaseModel):
    mes: str
    # Anterior ao mês civil de `hoje`: só nele se decide a sobra.
    mes_encerrado: bool
    # sem_conta | sem_credito | ok
    estado: str
    conta_vr_id: int | None
    credito: str
    # Nula em sem_conta.
    base_trabalho: str | None
    trabalho: BolsoSaida
    pessoal: BolsoSaida
    # Σ max(resta, 0) por bolso, sem compensar estouro (INV-25).
    sobra: str
    # Decisão vigente do mês (nula se não houve) e sua versão.
    decisao_destino: str | None
    decisao_versao: int | None
    # Só pré-seleciona a tela: sem decisão gravada, não há ajuste.
    destino_padrao: str
    # Saldo derivado normal da conta VR (acumula); nulo em sem_conta.
    saldo_total: str | None
    receita_caixa: str
    receita_beneficio: str
    receita_total: str


def _bolso(s: svc.Situacao, nome: str) -> BolsoSaida:
    return BolsoSaida(
        inicial=texto_dinheiro(getattr(s, f"inicial_{nome}")),
        ajuste=texto_dinheiro(getattr(s, f"ajuste_{nome}")),
        alocacao=texto_dinheiro(getattr(s, f"alocacao_{nome}")),
        consumo=texto_dinheiro(getattr(s, f"consumo_{nome}")),
        resta=texto_dinheiro(getattr(s, f"resta_{nome}")),
    )


@router.get("", response_model=SituacaoValeSaida)
async def situacao(
    conn: Conexao,
    sessao: Sessao,
    hoje: Annotated[date, Depends(hoje_civil)],
    mes: MesParam = None,
) -> SituacaoValeSaida:
    """Situação do vale no mês, derivada a cada consulta (ADR 052)."""
    alvo = _mes(mes, hoje)
    async with regras_do_banco():
        s = await svc.situacao(conn, sessao.user_id, alvo, hoje)
    return SituacaoValeSaida(
        mes=s.mes,
        mes_encerrado=s.mes_encerrado,
        estado=s.estado,
        conta_vr_id=s.conta_vr_id,
        credito=texto_dinheiro(s.credito),
        base_trabalho=_texto(s.base_trabalho),
        trabalho=_bolso(s, "trabalho"),
        pessoal=_bolso(s, "pessoal"),
        sobra=texto_dinheiro(s.sobra),
        decisao_destino=s.decisao_destino,
        decisao_versao=s.decisao_versao,
        destino_padrao=s.destino_padrao,
        saldo_total=_texto(s.saldo_total),
        receita_caixa=texto_dinheiro(s.receita_caixa),
        receita_beneficio=texto_dinheiro(s.receita_beneficio),
        receita_total=texto_dinheiro(s.receita_total),
    )


# ------------------------------------------------------------------ benefícios (VR e VA)


class BeneficioSaida(BaseModel):
    conta_id: int
    # Marca a conta do VR no mês; o VA e as demais não têm bolsos.
    vale_refeicao: bool
    receita_mes: str
    despesa_mes: str
    saldo_total: str


class BeneficiosSaida(BaseModel):
    mes: str
    itens: list[BeneficioSaida]


@router.get("/beneficios", response_model=BeneficiosSaida)
async def beneficios(
    conn: Conexao,
    sessao: Sessao,
    hoje: Annotated[date, Depends(hoje_civil)],
    mes: MesParam = None,
) -> BeneficiosSaida:
    """Contas de benefício vigentes (VR e VA) com receita e despesa do mês e saldo."""
    alvo = _mes(mes, hoje)
    async with regras_do_banco():
        itens = await svc.beneficios(conn, sessao.user_id, alvo, hoje)
    return BeneficiosSaida(
        mes=alvo,
        itens=[
            BeneficioSaida(
                conta_id=b.conta_id,
                vale_refeicao=b.vale_refeicao,
                receita_mes=texto_dinheiro(b.receita_mes),
                despesa_mes=texto_dinheiro(b.despesa_mes),
                saldo_total=texto_dinheiro(b.saldo_total),
            )
            for b in itens
        ],
    )


# ------------------------------------------------------------------ parâmetro


class ParametroValeEntrada(_CorpoSemUserId):
    # Conta de benefício do usuário, base 0 a 999999999.99 e vigência no dia 1 são do banco
    # (AB404/AB422); aqui só o que evita estouro de tipo (500).
    conta_id: IdConta
    base_trabalho: str = Field(pattern=PADRAO_BASE)
    destino_padrao: str
    vigente_desde: date

    _destino_limpo = field_validator("destino_padrao")(_texto_limpo)


class ParametroValeSaida(BaseModel):
    conta_id: int
    base_trabalho: str
    destino_padrao: str
    vigente_desde: date


def _saida_parametro(p: svc.Parametro) -> ParametroValeSaida:
    return ParametroValeSaida(
        conta_id=p.conta_id,
        base_trabalho=texto_dinheiro(p.base_trabalho),
        destino_padrao=p.destino_padrao,
        vigente_desde=p.vigente_desde,
    )


@router.get("/parametro", response_model=ParametroValeSaida | None)
async def obter_parametro(
    conn: Conexao,
    sessao: Sessao,
    hoje: Annotated[date, Depends(hoje_civil)],
    mes: MesParam = None,
) -> ParametroValeSaida | None:
    """Parâmetro vigente no mês (padrão: o corrente); nulo se nenhuma conta é o VR."""
    alvo = _mes(mes, hoje)
    async with regras_do_banco():
        p = await svc.parametro_vigente_em(conn, sessao.user_id, alvo)
    return None if p is None else _saida_parametro(p)


@router.put("/parametro", response_model=ParametroValeSaida, status_code=status.HTTP_200_OK)
async def gravar_parametro(
    entrada: ParametroValeEntrada, conn: Conexao, sessao: SessaoEscrita
) -> ParametroValeSaida:
    """Marca a conta do VR, a base e o destino padrão a partir de `vigente_desde`; idempotente."""
    async with regras_do_banco():
        gravado = await svc.gravar_parametro(
            conn,
            sessao.user_id,
            entrada.conta_id,
            Decimal(entrada.base_trabalho),
            entrada.destino_padrao,
            entrada.vigente_desde,
        )
    await conn.commit()
    return _saida_parametro(gravado)


# ------------------------------------------------------------------ decisão da sobra


class DecisaoValeEntrada(_CorpoSemUserId):
    # Mês AAAA-MM de um mês encerrado e destino trabalho|pessoal|nenhum são do banco (AB422).
    mes: str
    destino: str

    _limpos = field_validator("mes", "destino")(_texto_limpo)


class DecisaoValeSaida(BaseModel):
    mes: str
    destino: str
    # Cada nova decisão do mesmo mês é uma versão nova; repetir o destino vigente não cria.
    versao: int


class DecisaoHistoricoSaida(BaseModel):
    # Primeiro dia do mês decidido.
    mes: date
    destino: str
    versao: int
    # Só a maior versão de cada mês vale.
    vigente: bool


@router.get("/decisoes", response_model=list[DecisaoHistoricoSaida])
async def listar_decisoes(
    conn: Conexao, sessao: Sessao, mes: MesParam = None
) -> list[DecisaoHistoricoSaida]:
    """Histórico das decisões (todas as versões), do mês mais antigo ao mais novo."""
    filtro = mes_valido(mes) if mes is not None else None
    async with regras_do_banco():
        lista = await svc.listar_decisoes(conn, sessao.user_id, filtro)
    return [
        DecisaoHistoricoSaida(mes=d.mes, destino=d.destino, versao=d.versao, vigente=d.vigente)
        for d in lista
    ]


@router.put("/decisoes", response_model=DecisaoValeSaida, status_code=status.HTTP_200_OK)
async def gravar_decisao(
    entrada: DecisaoValeEntrada, conn: Conexao, sessao: SessaoEscrita
) -> DecisaoValeSaida:
    """Decide o destino da sobra de um mês encerrado; nunca move saldo (INV-25)."""
    mes = mes_valido(entrada.mes)
    async with regras_do_banco():
        versao = await svc.gravar_decisao(conn, sessao.user_id, mes, entrada.destino)
    await conn.commit()
    return DecisaoValeSaida(mes=mes, destino=entrada.destino, versao=versao)
