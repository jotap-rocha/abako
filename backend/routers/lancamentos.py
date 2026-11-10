"""Lançamentos (SPEC-004). Fino: valida, delega ao service, formata. Dinheiro sempre texto.

O valor chega positivo; o sinal e as pernas vêm do tipo, no banco (ADR 042). Crédito e repasse
são recusados até as SPECs 005 e 007; data futura é recusada.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query, Response, status
from pydantic import BaseModel, Field, field_validator

from backend.deps import Conexao, Sessao, SessaoEscrita
from backend.dinheiro import texto_dinheiro
from backend.erros_banco import regras_do_banco
from backend.routers.saldos import DATA_MINIMA
from backend.services import lancamentos as svc
from backend.tipos import TipoLancamento

router = APIRouter(prefix="/lancamentos", tags=["lancamentos"])

IdLancamento = Annotated[int, Path(ge=1, le=2**63 - 1)]
IdConta = Annotated[int, Field(ge=1, le=2**63 - 1)]
# Valor sempre positivo na entrada; o tipo dá o sinal.
PADRAO_POSITIVO = r"^[0-9]{1,12}(\.[0-9]{1,2})?$"


class _Campos(BaseModel):
    tipo: TipoLancamento
    data: date = Field(ge=DATA_MINIMA)
    # Débito, receita, transferência, investimento. No rendimento vem de bruto − imposto.
    valor: str | None = Field(default=None, pattern=PADRAO_POSITIVO)
    conta_id: IdConta
    conta_destino_id: IdConta | None = None
    bruto: str | None = Field(default=None, pattern=PADRAO_POSITIVO)
    imposto: str | None = Field(default=None, pattern=PADRAO_POSITIVO)
    descricao: str | None = None

    @field_validator("descricao")
    @classmethod
    def _descricao_aparada(cls, descricao: str | None) -> str | None:
        """Os 200 caracteres contam depois de tirar os espaços das pontas (como no banco)."""
        limpa = descricao.strip() if descricao else ""
        if len(limpa) > 200:
            raise ValueError("a descrição passa de 200 caracteres")
        return limpa or None

    def dados(self) -> svc.Dados:
        descricao = self.descricao
        return svc.Dados(
            tipo=self.tipo,
            data=self.data,
            valor=None if self.valor is None else Decimal(self.valor),
            conta_id=self.conta_id,
            conta_destino_id=self.conta_destino_id,
            bruto=None if self.bruto is None else Decimal(self.bruto),
            imposto=None if self.imposto is None else Decimal(self.imposto),
            descricao=descricao or None,
        )


class LancamentoEntrada(_Campos):
    # Gerada pelo front uma vez por formulário; repetir a mesma chave não duplica (INV-28).
    chave: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")


class LancamentoEdicao(_Campos):
    # A versão que o front leu; se outra edição veio antes, 409 (INV-29).
    versao: int = Field(ge=1)


class LancamentoSaida(BaseModel):
    transacao_id: int
    versao: int
    tipo: str
    data: date
    # Positivo, como foi digitado; no rendimento é o creditado (bruto − imposto).
    valor: str
    conta_id: int
    conta_destino_id: int | None
    bruto: str | None
    imposto: str | None
    descricao: str | None


def _saida(lanc: svc.Lancamento) -> LancamentoSaida:
    return LancamentoSaida(
        transacao_id=lanc.transacao_id,
        versao=lanc.versao,
        tipo=lanc.tipo,
        data=lanc.data,
        valor=texto_dinheiro(lanc.valor),
        conta_id=lanc.conta_id,
        conta_destino_id=lanc.conta_destino_id,
        bruto=None if lanc.bruto is None else texto_dinheiro(lanc.bruto),
        imposto=None if lanc.imposto is None else texto_dinheiro(lanc.imposto),
        descricao=lanc.descricao,
    )


async def _obter_ou_404(conn: Conexao, user_id: int, transacao_id: int) -> svc.Lancamento:
    lanc = await svc.obter(conn, user_id, transacao_id)
    if lanc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "lançamento não encontrado")
    return lanc


@router.post(
    "",
    response_model=LancamentoSaida,
    status_code=status.HTTP_201_CREATED,
    responses={200: {"model": LancamentoSaida, "description": "repetição da mesma chave"}},
)
async def criar(
    entrada: LancamentoEntrada, response: Response, conn: Conexao, sessao: SessaoEscrita
) -> LancamentoSaida:
    async with regras_do_banco():
        transacao_id, criou = await svc.gravar(
            conn, sessao.user_id, entrada.dados(), chave=entrada.chave
        )
    lanc = await svc.obter(conn, sessao.user_id, transacao_id)
    if lanc is None:
        # A chave é de um lançamento que já foi excluído: não ressuscita.
        raise HTTPException(status.HTTP_409_CONFLICT, "esse lançamento foi excluído")
    await conn.commit()
    if not criou:
        response.status_code = status.HTTP_200_OK
    return _saida(lanc)


@router.get("", response_model=list[LancamentoSaida])
async def listar(
    conn: Conexao,
    sessao: Sessao,
    conta_id: Annotated[int | None, Query(ge=1, le=2**63 - 1)] = None,
    de: Annotated[date | None, Query(ge=DATA_MINIMA)] = None,
    ate: Annotated[date | None, Query(ge=DATA_MINIMA)] = None,
    limite: Annotated[int, Query(ge=1, le=1000)] = 200,
) -> list[LancamentoSaida]:
    """Lançamentos vigentes, do mais recente para o mais antigo."""
    lista = await svc.listar(conn, sessao.user_id, conta_id=conta_id, de=de, ate=ate, limite=limite)
    return [_saida(lanc) for lanc in lista]


@router.get("/{transacao_id}", response_model=LancamentoSaida)
async def obter(transacao_id: IdLancamento, conn: Conexao, sessao: Sessao) -> LancamentoSaida:
    return _saida(await _obter_ou_404(conn, sessao.user_id, transacao_id))


@router.put("/{transacao_id}", response_model=LancamentoSaida)
async def editar(
    transacao_id: IdLancamento, entrada: LancamentoEdicao, conn: Conexao, sessao: SessaoEscrita
) -> LancamentoSaida:
    """Cria nova versão; a anterior fica no histórico e deixa de contar (INV-09)."""
    async with regras_do_banco():
        await svc.gravar(
            conn,
            sessao.user_id,
            entrada.dados(),
            transacao_id=transacao_id,
            versao=entrada.versao,
        )
    lanc = await _obter_ou_404(conn, sessao.user_id, transacao_id)
    await conn.commit()
    return _saida(lanc)


@router.delete("/{transacao_id}", status_code=status.HTTP_204_NO_CONTENT)
async def excluir(
    transacao_id: IdLancamento,
    conn: Conexao,
    sessao: SessaoEscrita,
    versao: Annotated[int, Query(ge=1)],
) -> None:
    """Exclusão lógica: nova versão marcada como excluída; deixa de contar no saldo."""
    async with regras_do_banco():
        await svc.excluir(conn, sessao.user_id, transacao_id, versao)
    await conn.commit()
