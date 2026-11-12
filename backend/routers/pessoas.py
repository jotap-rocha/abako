"""Pessoas (terceiros) e a receber por pessoa (SPEC-007, ADR 045). Fino: valida, delega, formata.

O `user_id` vem sempre da sessão (INV-13); dinheiro sempre texto (INV-14). O nome da pessoa é
dado pessoal: nunca em URL, log nem mensagem de erro (as mensagens do banco são literais).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query, status
from pydantic import BaseModel, Field, field_validator

from backend.deps import Conexao, Sessao, SessaoEscrita
from backend.dinheiro import texto_dinheiro
from backend.erros_banco import regras_do_banco
from backend.services import pessoas as svc

router = APIRouter(prefix="/pessoas", tags=["pessoas"])

IdPessoa = Annotated[int, Path(ge=1, le=2**63 - 1)]
# `versao` é integer no banco: acima disso o Postgres estouraria (500).
Versao = Annotated[int, Field(ge=1, le=2**31 - 1)]


class PessoaEntrada(BaseModel):
    nome: str = Field(min_length=1, max_length=80)

    @field_validator("nome", mode="before")
    @classmethod
    def _sem_espacos_nas_pontas(cls, nome: object) -> object:
        """Tira as pontas antes de contar de 1 a 80 (como o banco); vazio cai no min_length."""
        return nome.strip() if isinstance(nome, str) else nome


class PessoaEdicao(PessoaEntrada):
    # A versão que o front leu; se outra edição veio antes, 409.
    versao: Versao


class PessoaSaida(BaseModel):
    pessoa_id: int
    nome: str
    versao: int


class AReceberSaida(BaseModel):
    pessoa_id: int
    nome: str
    # D: total das compras da pessoa (parcelas futuras incluídas, sem as estornadas).
    divida: str
    # R: soma dos repasses vigentes.
    repassado: str
    # max(D - R, 0) e max(R - D, 0): nunca negativos (INV-33).
    a_receber: str
    credito_da_pessoa: str


def _saida(pessoa: svc.Pessoa) -> PessoaSaida:
    return PessoaSaida(pessoa_id=pessoa.pessoa_id, nome=pessoa.nome, versao=pessoa.versao)


def _saida_a_receber(r: svc.AReceber) -> AReceberSaida:
    return AReceberSaida(
        pessoa_id=r.pessoa_id,
        nome=r.nome,
        divida=texto_dinheiro(r.divida),
        repassado=texto_dinheiro(r.repassado),
        a_receber=texto_dinheiro(r.a_receber),
        credito_da_pessoa=texto_dinheiro(r.credito_da_pessoa),
    )


async def _gravada(conn: Conexao, user_id: int, pessoa_id: int) -> PessoaSaida:
    pessoa = await svc.obter(conn, user_id, pessoa_id)
    if pessoa is None:  # a função acabou de gravar: só falta se o banco estiver incoerente
        raise RuntimeError("pessoa gravada não encontrada")
    await conn.commit()
    return _saida(pessoa)


@router.post("", response_model=PessoaSaida, status_code=status.HTTP_201_CREATED)
async def criar(entrada: PessoaEntrada, conn: Conexao, sessao: SessaoEscrita) -> PessoaSaida:
    async with regras_do_banco():
        pessoa_id = await svc.gravar(conn, sessao.user_id, nome=entrada.nome)
    return await _gravada(conn, sessao.user_id, pessoa_id)


@router.get("", response_model=list[PessoaSaida])
async def listar(conn: Conexao, sessao: Sessao) -> list[PessoaSaida]:
    return [_saida(p) for p in await svc.listar(conn, sessao.user_id)]


# Declarada antes de "/{pessoa_id}" para "a-receber" não ser lido como id.
@router.get("/a-receber", response_model=list[AReceberSaida])
async def a_receber(conn: Conexao, sessao: Sessao) -> list[AReceberSaida]:
    """D, R, a receber e crédito de cada pessoa, derivados a cada consulta (INV-10, INV-33)."""
    return [_saida_a_receber(r) for r in await svc.a_receber(conn, sessao.user_id)]


@router.get("/{pessoa_id}", response_model=PessoaSaida)
async def obter(pessoa_id: IdPessoa, conn: Conexao, sessao: Sessao) -> PessoaSaida:
    pessoa = await svc.obter(conn, sessao.user_id, pessoa_id)
    if pessoa is None:
        # 404 também para pessoa de outro usuário: não revela que existe.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "pessoa não encontrada")
    return _saida(pessoa)


@router.get("/{pessoa_id}/a-receber", response_model=AReceberSaida)
async def a_receber_da_pessoa(pessoa_id: IdPessoa, conn: Conexao, sessao: Sessao) -> AReceberSaida:
    linhas = await svc.a_receber(conn, sessao.user_id, pessoa_id)
    if not linhas:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "pessoa não encontrada")
    return _saida_a_receber(linhas[0])


@router.put("/{pessoa_id}", response_model=PessoaSaida)
async def renomear(
    pessoa_id: IdPessoa, entrada: PessoaEdicao, conn: Conexao, sessao: SessaoEscrita
) -> PessoaSaida:
    """Cria nova versão; a anterior fica no histórico."""
    async with regras_do_banco():
        await svc.gravar(
            conn, sessao.user_id, nome=entrada.nome, pessoa_id=pessoa_id, versao=entrada.versao
        )
    return await _gravada(conn, sessao.user_id, pessoa_id)


@router.delete("/{pessoa_id}", status_code=status.HTTP_204_NO_CONTENT)
async def excluir(
    pessoa_id: IdPessoa,
    conn: Conexao,
    sessao: SessaoEscrita,
    versao: Annotated[int, Query(ge=1, le=2**31 - 1)],
) -> None:
    """Exclusão lógica; o banco recusa (422) enquanto houver compra ou repasse vigente dela."""
    async with regras_do_banco():
        await svc.excluir(conn, sessao.user_id, pessoa_id, versao)
    await conn.commit()
