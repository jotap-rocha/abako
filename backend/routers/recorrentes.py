"""Recorrentes, ocorrências do mês e vínculo com transação (SPEC-010, ADR 048). Fino: valida,
delega, formata.

O `user_id` vem sempre da sessão (INV-13); dinheiro sempre texto (INV-14). O nome do recorrente é
texto livre do usuário: nunca em URL, log nem mensagem de erro (as mensagens do banco são
literais). A ocorrência é derivada no banco; o vínculo é evento com histórico.
"""

from __future__ import annotations

import unicodedata
from datetime import date
from decimal import Decimal
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.deps import Conexao, Sessao, SessaoEscrita
from backend.dinheiro import texto_dinheiro
from backend.erros_banco import CABECALHO_CODIGO, regras_do_banco
from backend.services import gasto_real as svc_data
from backend.services import recorrentes as svc

router = APIRouter(prefix="/recorrentes", tags=["recorrentes"])

IdRecorrente = Annotated[int, Path(ge=1, le=2**63 - 1)]
IdConta = Annotated[int, Field(ge=1, le=2**63 - 1)]
IdTransacao = Annotated[int, Field(ge=1, le=2**63 - 1)]
# `versao` é integer no banco: acima disso o Postgres estouraria (500).
Versao = Annotated[int, Field(ge=1, le=2**31 - 1)]
# Até 2 casas; zero e o teto de 1 bilhão são recusados pelo banco (AB422).
PADRAO_VALOR = r"^[0-9]{1,12}(\.[0-9]{1,2})?$"
# O formato AAAA-MM é decidido só pelo banco (mes_inicio), sempre AB422 com X-Abako-Erro.
MesCaminho = Annotated[str, Path(description="Mês da ocorrência, AAAA-MM")]
MesConsulta = Annotated[
    str | None,
    Query(description="Mês AAAA-MM; padrão: o mês corrente em America/Sao_Paulo"),
]


def _mes_valido(mes: str) -> str:
    """Barra o que o banco nem chegaria a ler (muito longo; NUL e controle dariam 500 no driver)
    com o mesmo 422/AB422 literal que o banco devolve para formato inválido (mes_inicio)."""
    if len(mes) > 16 or any(unicodedata.category(c) == "Cc" for c in mes):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "o mês precisa estar no formato AAAA-MM",
            headers={CABECALHO_CODIGO: "AB422"},
        )
    return mes


def hoje_civil() -> date:
    """Dependência (substituível em teste): hoje em America/Sao_Paulo."""
    return svc_data.hoje_civil()


class RecorrenteEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nome: str = Field(min_length=1, max_length=80)
    # fixo = despesa recorrente; receita. Só em conta corrente (o banco recusa as demais).
    tipo: Literal["fixo", "receita"]
    valor: str = Field(pattern=PADRAO_VALOR)
    # 1 a 31 é do banco (AB422); aqui só o que evita estouro de tipo (500).
    dia: int = Field(ge=-(2**31), le=2**31 - 1)
    conta_id: IdConta
    mes_inicio: str = Field(max_length=16)
    mes_fim: str | None = Field(default=None, max_length=16)

    @model_validator(mode="before")
    @classmethod
    def _sem_user_id(cls, corpo: Any) -> Any:
        """`user_id` no corpo é descartado: a sessão manda (INV-13). Outra chave é 422."""
        if isinstance(corpo, dict):
            return {k: v for k, v in corpo.items() if k != "user_id"}
        return corpo

    @field_validator("nome", mode="before")
    @classmethod
    def _sem_espacos_nas_pontas(cls, nome: object) -> object:
        """Tira as pontas antes de contar de 1 a 80 (como o banco); vazio cai no min_length."""
        if not isinstance(nome, str):
            return nome
        limpo = nome.strip()
        # NUL e demais caracteres de controle: o Postgres recusa NUL (seria 500) e o resto
        # sujaria listas e telas. A mensagem não repete o valor.
        if any(unicodedata.category(c) == "Cc" for c in limpo):
            raise ValueError("o nome não pode ter caracteres de controle")
        return limpo

    @field_validator("mes_inicio", "mes_fim")
    @classmethod
    def _mes_sem_controle(cls, mes: str | None) -> str | None:
        """O formato é do banco (AB422); aqui só o que o driver recusaria com 500 (NUL)."""
        if mes is not None and any(unicodedata.category(c) == "Cc" for c in mes):
            raise ValueError("o mês precisa estar no formato AAAA-MM")
        return mes


class RecorrenteEdicao(RecorrenteEntrada):
    # A versão que o front leu; se outra edição veio antes, 409.
    versao: Versao


class VinculoEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transacao_id: IdTransacao

    @model_validator(mode="before")
    @classmethod
    def _sem_user_id(cls, corpo: Any) -> Any:
        if isinstance(corpo, dict):
            return {k: v for k, v in corpo.items() if k != "user_id"}
        return corpo


class RecorrenteSaida(BaseModel):
    recorrente_id: int
    nome: str
    tipo: str
    valor: str
    dia: int
    conta_id: int
    # AAAA-MM; o fim é opcional.
    mes_inicio: str
    mes_fim: str | None
    versao: int


class OcorrenciaSaida(BaseModel):
    recorrente_id: int
    nome: str
    tipo: str
    conta_id: int
    mes: str
    # Dia do cadastro, ou o último dia válido do mês (ADR 048 item 2).
    data: date
    valor_esperado: str
    # Valor esperado até vincular; vinculada, o valor absoluto da transação.
    valor: str
    transacao_id: int | None
    vinculada: bool


def _saida(r: svc.Recorrente) -> RecorrenteSaida:
    return RecorrenteSaida(
        recorrente_id=r.recorrente_id,
        nome=r.nome,
        tipo=r.tipo,
        valor=texto_dinheiro(r.valor),
        dia=r.dia,
        conta_id=r.conta_id,
        mes_inicio=r.mes_inicio,
        mes_fim=r.mes_fim,
        versao=r.versao,
    )


def _saida_ocorrencia(o: svc.Ocorrencia) -> OcorrenciaSaida:
    return OcorrenciaSaida(
        recorrente_id=o.recorrente_id,
        nome=o.nome,
        tipo=o.tipo,
        conta_id=o.conta_id,
        mes=o.mes,
        data=o.data,
        valor_esperado=texto_dinheiro(o.valor_esperado),
        valor=texto_dinheiro(o.valor),
        transacao_id=o.transacao_id,
        vinculada=o.vinculada,
    )


async def _gravado(conn: Conexao, user_id: int, recorrente_id: int) -> RecorrenteSaida:
    r = await svc.obter(conn, user_id, recorrente_id)
    if r is None:  # a função acabou de gravar: só falta se o banco estiver incoerente
        raise RuntimeError("recorrente gravado não encontrado")
    await conn.commit()
    return _saida(r)


async def _ocorrencia_do_vinculo(
    conn: Conexao, user_id: int, recorrente_id: int, mes: str
) -> OcorrenciaSaida:
    lista = await svc.ocorrencias_do_mes(conn, user_id, mes, recorrente_id)
    if not lista:  # o vínculo só passa dentro do período; sem linha é banco incoerente
        raise RuntimeError("ocorrência vinculada não encontrada")
    await conn.commit()
    return _saida_ocorrencia(lista[0])


@router.post("", response_model=RecorrenteSaida, status_code=status.HTTP_201_CREATED)
async def criar(
    entrada: RecorrenteEntrada, conn: Conexao, sessao: SessaoEscrita
) -> RecorrenteSaida:
    async with regras_do_banco():
        recorrente_id = await svc.gravar(conn, sessao.user_id, **_campos(entrada))
    return await _gravado(conn, sessao.user_id, recorrente_id)


def _campos(entrada: RecorrenteEntrada) -> dict[str, Any]:
    return {
        "nome": entrada.nome,
        "tipo": entrada.tipo,
        "valor": Decimal(entrada.valor),
        "dia": entrada.dia,
        "conta_id": entrada.conta_id,
        "mes_inicio": entrada.mes_inicio,
        "mes_fim": entrada.mes_fim,
    }


@router.get("", response_model=list[RecorrenteSaida])
async def listar(conn: Conexao, sessao: Sessao) -> list[RecorrenteSaida]:
    return [_saida(r) for r in await svc.listar(conn, sessao.user_id)]


# Declarada antes de "/{recorrente_id}" para "ocorrencias" não ser lido como id.
@router.get("/ocorrencias", response_model=list[OcorrenciaSaida])
async def ocorrencias(
    conn: Conexao,
    sessao: Sessao,
    hoje: Annotated[date, Depends(hoje_civil)],
    mes: MesConsulta = None,
) -> list[OcorrenciaSaida]:
    """Ocorrências do mês (uma por recorrente vigente no período), derivadas a cada consulta."""
    alvo = _mes_valido(mes) if mes is not None else hoje.strftime("%Y-%m")
    async with regras_do_banco():
        lista = await svc.ocorrencias_do_mes(conn, sessao.user_id, alvo)
    return [_saida_ocorrencia(o) for o in lista]


@router.get("/{recorrente_id}", response_model=RecorrenteSaida)
async def obter(recorrente_id: IdRecorrente, conn: Conexao, sessao: Sessao) -> RecorrenteSaida:
    r = await svc.obter(conn, sessao.user_id, recorrente_id)
    if r is None:
        # 404 também para recorrente de outro usuário: não revela que existe.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "recorrente não encontrado")
    return _saida(r)


@router.put("/{recorrente_id}", response_model=RecorrenteSaida)
async def editar(
    recorrente_id: IdRecorrente, entrada: RecorrenteEdicao, conn: Conexao, sessao: SessaoEscrita
) -> RecorrenteSaida:
    """Cria nova versão; a anterior fica no histórico. Vale para as ocorrências não vinculadas."""
    async with regras_do_banco():
        await svc.gravar(
            conn,
            sessao.user_id,
            **_campos(entrada),
            recorrente_id=recorrente_id,
            versao=entrada.versao,
        )
    return await _gravado(conn, sessao.user_id, recorrente_id)


@router.delete("/{recorrente_id}", status_code=status.HTTP_204_NO_CONTENT)
async def excluir(
    recorrente_id: IdRecorrente,
    conn: Conexao,
    sessao: SessaoEscrita,
    versao: Annotated[int, Query(ge=1, le=2**31 - 1)],
) -> None:
    """Exclusão lógica; o histórico dos vínculos fica."""
    async with regras_do_banco():
        await svc.excluir(conn, sessao.user_id, recorrente_id, versao)
    await conn.commit()


@router.put("/{recorrente_id}/ocorrencias/{mes}/vinculo", response_model=OcorrenciaSaida)
async def vincular(
    recorrente_id: IdRecorrente,
    mes: MesCaminho,
    entrada: VinculoEntrada,
    conn: Conexao,
    sessao: SessaoEscrita,
) -> OcorrenciaSaida:
    """Liga a transação (mesmo tipo e conta) à ocorrência; repetir o mesmo vínculo é idempotente."""
    _mes_valido(mes)
    async with regras_do_banco():
        await svc.vincular(conn, sessao.user_id, recorrente_id, mes, entrada.transacao_id)
        return await _ocorrencia_do_vinculo(conn, sessao.user_id, recorrente_id, mes)


@router.delete("/{recorrente_id}/ocorrencias/{mes}/vinculo", response_model=OcorrenciaSaida)
async def desvincular(
    recorrente_id: IdRecorrente, mes: MesCaminho, conn: Conexao, sessao: SessaoEscrita
) -> OcorrenciaSaida:
    """Desfaz o vínculo (evento novo, o histórico fica); a ocorrência volta ao valor esperado."""
    _mes_valido(mes)
    async with regras_do_banco():
        await svc.desvincular(conn, sessao.user_id, recorrente_id, mes)
        return await _ocorrencia_do_vinculo(conn, sessao.user_id, recorrente_id, mes)
