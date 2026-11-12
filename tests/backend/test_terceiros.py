"""API de terceiros e repasse (SPEC-007, ADR 045): rotas de pessoa, compra de terceiro, repasse,
a receber por pessoa e fatura própria + terceiros. Valores esperados vêm de F-REP-01..04, F-FAT-01
e F-LIM-01 (calculados à mão); dinheiro é texto; o nome da pessoa nunca vai a log nem a erro."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.backend.conftest import ORIGEM, Usuario, apagar_usuarios, criar_usuario, logar
from tests.backend.test_credito_api import (
    comprar,
    criar_cartao,
    criar_conta,
    criar_linha,
    escrita,
    saldo,
)

pytestmark = pytest.mark.banco

# Fechamento dia 10 (criar_cartao): compra até 10/03 cai na fatura 2026-03, e assim por diante.
C1, C2, C3, C4 = "2026-03", "2026-04", "2026-05", "2026-06"
DATA_C1 = "2026-03-05"


@pytest.fixture
def outro_usuario(esquema: str) -> Iterator[Usuario]:
    u = criar_usuario(esquema, "o")
    yield u
    apagar_usuarios(esquema, [u])


def nova_pessoa(client: TestClient, csrf: str, nome: str) -> int:
    r = client.post("/api/pessoas", json={"nome": nome}, headers=escrita(csrf))
    assert r.status_code == 201, r.text
    pessoa_id: int = r.json()["pessoa_id"]
    return pessoa_id


def repassar(
    client: TestClient,
    csrf: str,
    conta: int,
    pessoa: int | None,
    valor: str,
    chave: str,
    data: str = "2026-03-06",
) -> Any:
    return client.post(
        "/api/lancamentos",
        json={
            "chave": chave,
            "tipo": "repasse",
            "data": data,
            "valor": valor,
            "conta_id": conta,
            "pessoa_id": pessoa,
        },
        headers=escrita(csrf),
    )


def a_receber(client: TestClient) -> dict[int, dict[str, Any]]:
    r = client.get("/api/pessoas/a-receber")
    assert r.status_code == 200, r.text
    return {linha["pessoa_id"]: linha for linha in r.json()}


def situacao(client: TestClient, pessoa: int) -> dict[str, str]:
    """Só os quatro valores, para comparar com o `esperado` das fixtures."""
    linha = a_receber(client)[pessoa]
    return {k: linha[k] for k in ("divida", "repassado", "a_receber", "credito_da_pessoa")}


def fatura(client: TestClient, cartao: int, competencia: str) -> dict[str, Any]:
    r = client.get(f"/api/cartoes/{cartao}/faturas/{competencia}")
    assert r.status_code == 200, r.text
    corpo: dict[str, Any] = r.json()
    return corpo


def resumo(f: dict[str, Any]) -> dict[str, str]:
    return {k: f[k] for k in ("total", "propria", "terceiros")}


def cenario(client: TestClient, usuario: Usuario) -> tuple[str, int, int]:
    csrf = logar(client, usuario)
    cartao = criar_cartao(client, csrf, criar_linha(client, csrf))
    corrente = criar_conta(client, csrf, "Corrente")
    return csrf, cartao, corrente


# ------------------------------------------------------------------ cadastro de pessoa


def test_cadastro_de_pessoa_pela_api(client: TestClient, usuario: Usuario) -> None:
    """SPEC-007-AC-9 pela API: cria, lista, renomeia (versão), nome repetido e inválido."""
    csrf = logar(client, usuario)
    bia = nova_pessoa(client, csrf, "  Bia  ")
    assert client.get("/api/pessoas").json() == [{"pessoa_id": bia, "nome": "Bia", "versao": 1}]
    assert client.get(f"/api/pessoas/{bia}").json()["nome"] == "Bia"

    r = client.put(
        f"/api/pessoas/{bia}", json={"nome": "Beatriz", "versao": 1}, headers=escrita(csrf)
    )
    assert r.status_code == 200 and (r.json()["nome"], r.json()["versao"]) == ("Beatriz", 2)
    r = client.put(f"/api/pessoas/{bia}", json={"nome": "X", "versao": 1}, headers=escrita(csrf))
    assert r.status_code == 409 and r.headers["X-Abako-Erro"] == "AB409"

    # Nome repetido sem diferenciar maiúsculas: 409/AB410; vazio e acima de 80: 422.
    r = client.post("/api/pessoas", json={"nome": "BEATRIZ"}, headers=escrita(csrf))
    assert r.status_code == 409 and r.headers["X-Abako-Erro"] == "AB410"
    for nome in ("", "   ", "n" * 81):
        r = client.post("/api/pessoas", json={"nome": nome}, headers=escrita(csrf))
        assert r.status_code == 422, nome
    assert len(client.get("/api/pessoas").json()) == 1

    # Pessoa inexistente: 404 (rota fina, regra do banco).
    assert client.get("/api/pessoas/999999999").status_code == 404
    r = client.put("/api/pessoas/999999999", json={"nome": "Z", "versao": 1}, headers=escrita(csrf))
    assert r.status_code == 404 and r.headers["X-Abako-Erro"] == "AB404"


def test_exclusao_de_pessoa(client: TestClient, usuario: Usuario) -> None:
    """SPEC-007-AC-9: com compra ou repasse vigente é recusada (422) e nada muda; sem movimento
    é exclusão lógica (204), a pessoa some da lista e o nome é liberado."""
    csrf, cartao, corrente = cenario(client, usuario)
    com_compra = nova_pessoa(client, csrf, "Com compra")
    com_repasse = nova_pessoa(client, csrf, "Com repasse")
    livre = nova_pessoa(client, csrf, "Livre")
    assert (
        comprar(client, csrf, cartao, data=DATA_C1, pessoa_id=com_compra, parcelas=1).status_code
        == 201
    )
    rep = repassar(client, csrf, corrente, com_repasse, "10.00", "repasse-0001").json()

    for pessoa in (com_compra, com_repasse):
        r = client.delete(f"/api/pessoas/{pessoa}", params={"versao": 1}, headers=escrita(csrf))
        assert r.status_code == 422 and r.headers["X-Abako-Erro"] == "AB422", r.text
        assert "não pode ser excluída" in r.json()["detail"]
    assert len(client.get("/api/pessoas").json()) == 3

    # Apagar o repasse (lógico) libera a pessoa.
    r = client.delete(
        f"/api/lancamentos/{rep['transacao_id']}", params={"versao": 1}, headers=escrita(csrf)
    )
    assert r.status_code == 204
    r = client.delete(f"/api/pessoas/{com_repasse}", params={"versao": 1}, headers=escrita(csrf))
    assert r.status_code == 204
    r = client.delete(f"/api/pessoas/{livre}", params={"versao": 7}, headers=escrita(csrf))
    assert r.status_code == 409 and r.headers["X-Abako-Erro"] == "AB409"
    r = client.delete(f"/api/pessoas/{livre}", params={"versao": 1}, headers=escrita(csrf))
    assert r.status_code == 204
    assert [p["nome"] for p in client.get("/api/pessoas").json()] == ["Com compra"]
    assert client.get(f"/api/pessoas/{livre}").status_code == 404
    assert client.get(f"/api/pessoas/{livre}/a-receber").status_code == 404
    nova_pessoa(client, csrf, "Livre")  # o nome da excluída volta a ficar livre


# ------------------------------------------------------------------ a receber e repasse


def test_a_receber_e_credito_f_rep_01(client: TestClient, usuario: Usuario) -> None:
    """SPEC-007-AC-3 e AC-8: repasse acima da dívida vira crédito da pessoa; compra nova o abate;
    o saldo da conta corrente sobe pelos repasses."""
    csrf, cartao, corrente = cenario(client, usuario)
    b = nova_pessoa(client, csrf, "Pessoa B")

    def compra(valor: str, chave: str) -> None:
        r = comprar(
            client, csrf, cartao, chave=chave, data=DATA_C1, valor=valor, parcelas=1, pessoa_id=b
        )
        assert r.status_code == 201, r.text
        assert r.json()["pessoa_id"] == b

    compra("400.00", "compra-0001")
    assert situacao(client, b) == {
        "divida": "400.00",
        "repassado": "0.00",
        "a_receber": "400.00",
        "credito_da_pessoa": "0.00",
    }
    r = repassar(client, csrf, corrente, b, "250.00", "repasse-0001")
    assert r.status_code == 201, r.text
    assert (r.json()["tipo"], r.json()["pessoa_id"], r.json()["valor"]) == ("repasse", b, "250.00")
    assert situacao(client, b) == {
        "divida": "400.00",
        "repassado": "250.00",
        "a_receber": "150.00",
        "credito_da_pessoa": "0.00",
    }
    assert repassar(client, csrf, corrente, b, "200.00", "repasse-0002").status_code == 201
    assert situacao(client, b) == {
        "divida": "400.00",
        "repassado": "450.00",
        "a_receber": "0.00",
        "credito_da_pessoa": "50.00",
    }
    assert saldo(client, corrente, "2026-03-31") == "450.00"
    compra("30.00", "compra-0002")
    assert situacao(client, b) == {
        "divida": "430.00",
        "repassado": "450.00",
        "a_receber": "0.00",
        "credito_da_pessoa": "20.00",
    }
    compra("100.00", "compra-0003")
    assert situacao(client, b) == {
        "divida": "530.00",
        "repassado": "450.00",
        "a_receber": "80.00",
        "credito_da_pessoa": "0.00",
    }
    # A rota de uma pessoa só devolve o mesmo que a lista, com o nome.
    um = client.get(f"/api/pessoas/{b}/a-receber").json()
    assert um == a_receber(client)[b] and um["nome"] == "Pessoa B"


def test_repasse_regras_pela_api(client: TestClient, usuario: Usuario) -> None:
    """SPEC-007-AC-8: só em conta corrente, com pessoa; edita (versão) e exclui (lógico), e o a
    receber volta ao que era; repasse não entra em fatura nem em limite."""
    csrf, cartao, corrente = cenario(client, usuario)
    reserva = criar_conta(client, csrf, "Reserva", "reserva")
    r = client.post(
        "/api/contas",
        json={"nome": "Vale", "tipo": "beneficio", "conta_beneficio": True},
        headers=escrita(csrf),
    )
    assert r.status_code == 201, r.text
    beneficio = r.json()["conta_id"]
    b = nova_pessoa(client, csrf, "Pessoa B")
    assert (
        comprar(
            client, csrf, cartao, data=DATA_C1, valor="100.00", parcelas=1, pessoa_id=b
        ).status_code
        == 201
    )

    # Recusas (nada é gravado): sem pessoa, cartão, reserva, benefício, data futura, valor <= 0.
    assert repassar(client, csrf, corrente, None, "10.00", "repasse-0001").status_code == 422
    for conta, chave in ((cartao, "repasse-0002"), (reserva, "repasse-0003")):
        r = repassar(client, csrf, conta, b, "10.00", chave)
        assert r.status_code == 422 and r.headers["X-Abako-Erro"] == "AB422", r.text
    assert repassar(client, csrf, beneficio, b, "10.00", "repasse-0004").status_code == 422
    assert (
        repassar(client, csrf, corrente, b, "10.00", "repasse-0005", "2999-01-01").status_code
        == 422
    )
    assert repassar(client, csrf, corrente, b, "0", "repasse-0006").status_code == 422
    tipos = [i["tipo"] for i in client.get("/api/lancamentos").json()]
    assert tipos == ["credito"]

    r = repassar(client, csrf, corrente, b, "40.00", "repasse-0007")
    assert r.status_code == 201, r.text
    rep = r.json()
    assert situacao(client, b)["a_receber"] == "60.00"
    assert saldo(client, corrente, "2026-03-31") == "40.00"
    # O repasse não é compra: fatura e limite ficam como estavam.
    assert resumo(fatura(client, cartao, C1)) == {
        "total": "100.00",
        "propria": "0.00",
        "terceiros": "100.00",
    }

    # Edição cria versão 2; a versão velha dá 409.
    corpo = {
        "tipo": "repasse",
        "data": "2026-03-06",
        "valor": "70.00",
        "conta_id": corrente,
        "pessoa_id": b,
        "versao": 1,
    }
    r = client.put(f"/api/lancamentos/{rep['transacao_id']}", json=corpo, headers=escrita(csrf))
    assert r.status_code == 200 and (r.json()["versao"], r.json()["valor"]) == (2, "70.00")
    assert situacao(client, b)["a_receber"] == "30.00"
    r = client.put(f"/api/lancamentos/{rep['transacao_id']}", json=corpo, headers=escrita(csrf))
    assert r.status_code == 409 and r.headers["X-Abako-Erro"] == "AB409"

    # Exclusão lógica: o a receber volta a 100,00 e o saldo da conta a 0,00.
    r = client.delete(
        f"/api/lancamentos/{rep['transacao_id']}", params={"versao": 2}, headers=escrita(csrf)
    )
    assert r.status_code == 204
    assert situacao(client, b)["a_receber"] == "100.00"
    assert saldo(client, corrente, "2026-03-31") == "0.00"


def test_a_receber_varias_pessoas_f_rep_03(client: TestClient, usuario: Usuario) -> None:
    """SPEC-007-AC-1 e AC-4: várias pessoas, fatura própria + terceiros e limite com terceiros."""
    csrf = logar(client, usuario)
    linha = criar_linha(client, csrf, limite="5000.00")
    cartao = criar_cartao(client, csrf, linha)
    corrente = criar_conta(client, csrf, "Corrente")
    p = {n: nova_pessoa(client, csrf, f"Pessoa {n.upper()}") for n in "bcdef"}

    compras = [
        (None, "600.00", 1),
        (p["b"], "400.00", 1),
        (p["c"], "90.00", 3),
        (p["e"], "60.00", 1),
    ]
    for i, (pessoa, total, parcelas) in enumerate(compras):
        r = comprar(
            client,
            csrf,
            cartao,
            chave=f"compra-{i:04d}",
            data=DATA_C1,
            valor=total,
            parcelas=parcelas,
            pessoa_id=pessoa,
        )
        assert r.status_code == 201, r.text
    for i, (pessoa, valor) in enumerate([(p["b"], "250.00"), (p["d"], "40.00"), (p["e"], "60.00")]):
        assert (
            repassar(client, csrf, corrente, pessoa, valor, f"repasse-{i:04d}").status_code == 201
        )

    zero = {"divida": "0.00", "repassado": "0.00", "a_receber": "0.00", "credito_da_pessoa": "0.00"}
    assert situacao(client, p["b"]) == {
        "divida": "400.00",
        "repassado": "250.00",
        "a_receber": "150.00",
        "credito_da_pessoa": "0.00",
    }
    assert situacao(client, p["c"]) == {
        "divida": "90.00",
        "repassado": "0.00",
        "a_receber": "90.00",
        "credito_da_pessoa": "0.00",
    }
    assert situacao(client, p["d"]) == {
        "divida": "0.00",
        "repassado": "40.00",
        "a_receber": "0.00",
        "credito_da_pessoa": "40.00",
    }
    assert situacao(client, p["e"]) == {
        "divida": "60.00",
        "repassado": "60.00",
        "a_receber": "0.00",
        "credito_da_pessoa": "0.00",
    }
    assert situacao(client, p["f"]) == zero  # sem movimento aparece zerada
    todas = a_receber(client)
    assert sum(Decimal(x["a_receber"]) for x in todas.values()) == Decimal("240.00")
    assert sum(Decimal(x["credito_da_pessoa"]) for x in todas.values()) == Decimal("40.00")

    f1 = fatura(client, cartao, C1)
    assert resumo(f1) == {"total": "1090.00", "propria": "600.00", "terceiros": "490.00"}
    assert resumo(fatura(client, cartao, C2)) == {
        "total": "30.00",
        "propria": "0.00",
        "terceiros": "30.00",
    }
    # Cada item diz de quem é (nula = própria); o nome não vai na fatura.
    por_valor = {i["valor"]: i["pessoa_id"] for i in f1["itens"] if i["parcelas"] == 1}
    assert por_valor == {"600.00": None, "400.00": p["b"], "60.00": p["e"]}
    assert {i["pessoa_id"] for i in f1["itens"] if i["parcelas"] == 3} == {p["c"]}
    r = client.get(f"/api/linhas-credito/{linha}/limite")
    assert r.json() == {"limite": "5000.00", "usado": "1150.00", "disponivel": "3850.00"}


def test_fatura_propria_mais_terceiros_f_fat_01(client: TestClient, usuario: Usuario) -> None:
    """SPEC-007-AC-4: 600,00 própria + 400,00 de terceiro = 1000,00; a receber 150,00 após o
    repasse de 250,00 (F-FAT-01)."""
    csrf = logar(client, usuario)
    linha = criar_linha(client, csrf, limite="5000.00")
    x = criar_cartao(client, csrf, linha, "Cartão X")
    y = criar_cartao(client, csrf, linha, "Cartão Y")
    corrente = criar_conta(client, csrf, "Corrente")
    b = nova_pessoa(client, csrf, "Pessoa B")

    comprar(client, csrf, x, chave="compra-0001", data=DATA_C1, valor="600.00", parcelas=1)
    comprar(
        client, csrf, y, chave="compra-0002", data=DATA_C1, valor="400.00", parcelas=1, pessoa_id=b
    )
    repassar(client, csrf, corrente, b, "250.00", "repasse-0001")
    assert resumo(fatura(client, x, C1)) == {
        "total": "600.00",
        "propria": "600.00",
        "terceiros": "0.00",
    }
    assert resumo(fatura(client, y, C1)) == {
        "total": "400.00",
        "propria": "0.00",
        "terceiros": "400.00",
    }
    assert situacao(client, b)["a_receber"] == "150.00"


def test_limite_f_lim_01_isolado(client: TestClient, usuario: Usuario) -> None:
    """SPEC-007-AC-4: exatamente F-LIM-01 (1200,00 em 4x própria; 300,00 da pessoa_b)."""
    csrf = logar(client, usuario)
    linha = criar_linha(client, csrf, limite="5000.00")
    x = criar_cartao(client, csrf, linha, "Cartão X")
    y = criar_cartao(client, csrf, linha, "Cartão Y")
    b = nova_pessoa(client, csrf, "Pessoa B")
    comprar(client, csrf, x, chave="compra-0001", data=DATA_C1, valor="1200.00", parcelas=4)
    comprar(
        client, csrf, y, chave="compra-0002", data=DATA_C1, valor="300.00", parcelas=1, pessoa_id=b
    )
    r = client.get(f"/api/linhas-credito/{linha}/limite")
    assert r.json() == {"limite": "5000.00", "usado": "1500.00", "disponivel": "3500.00"}


def test_estorno_de_compra_de_terceiro_f_rep_02(client: TestClient, usuario: Usuario) -> None:
    """SPEC-007-AC-5: a dívida cai pelo T inteiro, o excedente do repasse vira crédito da pessoa
    e o crédito P fica no grupo terceiros da fatura c3; a própria não é reduzida."""
    csrf, cartao, corrente = cenario(client, usuario)
    b = nova_pessoa(client, csrf, "Pessoa B")
    compra = comprar(
        client,
        csrf,
        cartao,
        chave="compra-0001",
        data=DATA_C1,
        valor="400.00",
        parcelas=4,
        pessoa_id=b,
    ).json()
    proprio = comprar(
        client, csrf, cartao, chave="compra-0002", data="2026-05-05", valor="50.00", parcelas=1
    )
    assert proprio.status_code == 201, proprio.text
    assert repassar(client, csrf, corrente, b, "100.00", "repasse-0001").status_code == 201
    r = client.post(
        "/api/lancamentos",
        json={
            "chave": "pgto-0001",
            "tipo": "transferencia",
            "data": "2026-03-20",
            "valor": "150.00",
            "conta_id": corrente,
            "conta_destino_id": cartao,
        },
        headers=escrita(csrf),
    )
    assert r.status_code == 201, r.text
    assert situacao(client, b) == {
        "divida": "400.00",
        "repassado": "100.00",
        "a_receber": "300.00",
        "credito_da_pessoa": "0.00",
    }

    # A compra com parte paga não se edita nem se exclui, também sendo de terceiro (ADR 044).
    edicao = {
        "tipo": "credito",
        "data": DATA_C1,
        "valor": "400.00",
        "parcelas": 4,
        "conta_id": cartao,
        "pessoa_id": None,
        "versao": 1,
    }
    r = client.put(f"/api/lancamentos/{compra['transacao_id']}", json=edicao, headers=escrita(csrf))
    assert r.status_code == 422 and "parte paga" in r.json()["detail"], r.text

    r = client.post(
        f"/api/lancamentos/{compra['transacao_id']}/estorno",
        json={"versao": 1, "data": "2026-04-25"},
        headers=escrita(csrf),
    )
    assert r.status_code == 201, r.text
    assert r.json() | {"estorno_id": 0} == {
        "estorno_id": 0,
        "competencia_credito": C3,
        "total": "400.00",
        "pago": "150.00",
        "limite_devolvido": "250.00",
    }
    assert situacao(client, b) == {
        "divida": "0.00",
        "repassado": "100.00",
        "a_receber": "0.00",
        "credito_da_pessoa": "100.00",
    }
    esperado = {
        C1: {"total": "100.00", "propria": "0.00", "terceiros": "100.00"},
        C2: {"total": "100.00", "propria": "0.00", "terceiros": "100.00"},
        C3: {"total": "-100.00", "propria": "50.00", "terceiros": "-150.00"},
        C4: {"total": "0.00", "propria": "0.00", "terceiros": "0.00"},
    }
    for competencia, valores in esperado.items():
        assert resumo(fatura(client, cartao, competencia)) == valores, competencia
    credito = [i for i in fatura(client, cartao, C3)["itens"] if i["valor"] == "-150.00"]
    assert [i["pessoa_id"] for i in credito] == [b]


# ------------------------------------------------------------------ divisão (INV-32)


def test_divisao_rejeitada(client: TestClient, usuario: Usuario) -> None:
    """SPEC-007-AC-11, INV-32, F-REP-04: corpo que reparte a compra entre próprio e pessoa é 422 e
    nada é gravado; pessoa fora do cartão é recusada; a compra inteira da pessoa é aceita."""
    csrf, cartao, corrente = cenario(client, usuario)
    b = nova_pessoa(client, csrf, "Pessoa B")
    base = {
        "chave": "compra-0001",
        "tipo": "credito",
        "data": DATA_C1,
        "valor": "100.00",
        "parcelas": 1,
        "conta_id": cartao,
    }
    divisao = [
        {"pessoa_id": None, "valor": "60.00"},
        {"pessoa_id": b, "valor": "40.00"},
    ]
    for extra in (
        {"divisao": divisao},
        {"partes": divisao, "pessoa_id": b},
        {"pessoas": [b, b]},
        {"rateio": divisao},
    ):
        r = client.post("/api/lancamentos", json=base | extra, headers=escrita(csrf))
        assert r.status_code == 422, (extra, r.text)
        assert "dividida" in r.text
    # Mais de um dono no campo da pessoa também não passa.
    r = client.post("/api/lancamentos", json=base | {"pessoa_id": [b, b]}, headers=escrita(csrf))
    assert r.status_code == 422
    # Terceiro fora do cartão (débito) é recusado pelo banco.
    r = client.post(
        "/api/lancamentos",
        json={
            "chave": "debito-0001",
            "tipo": "debito",
            "data": DATA_C1,
            "valor": "100.00",
            "conta_id": corrente,
            "pessoa_id": b,
        },
        headers=escrita(csrf),
    )
    assert r.status_code == 422 and r.headers["X-Abako-Erro"] == "AB422", r.text
    assert client.get("/api/lancamentos").json() == []

    # Aceita: a compra inteira da pessoa.
    r = client.post("/api/lancamentos", json=base | {"pessoa_id": b}, headers=escrita(csrf))
    assert r.status_code == 201, r.text
    assert situacao(client, b) == {
        "divida": "100.00",
        "repassado": "0.00",
        "a_receber": "100.00",
        "credito_da_pessoa": "0.00",
    }


def test_idempotencia_considera_a_pessoa(client: TestClient, usuario: Usuario) -> None:
    """INV-28: repetir chave e corpo (com a pessoa) não duplica; outra pessoa com a chave: 422."""
    csrf, cartao, _ = cenario(client, usuario)
    b = nova_pessoa(client, csrf, "Pessoa B")
    c = nova_pessoa(client, csrf, "Pessoa C")
    r1 = comprar(client, csrf, cartao, data=DATA_C1, parcelas=1, pessoa_id=b)
    r2 = comprar(client, csrf, cartao, data=DATA_C1, parcelas=1, pessoa_id=b)
    assert (r1.status_code, r2.status_code) == (201, 200)
    assert r1.json()["transacao_id"] == r2.json()["transacao_id"]
    assert comprar(client, csrf, cartao, data=DATA_C1, parcelas=1, pessoa_id=c).status_code == 422
    assert situacao(client, b)["divida"] == "100.00"
    assert situacao(client, c)["divida"] == "0.00"


def test_troca_de_pessoa_na_edicao(client: TestClient, usuario: Usuario) -> None:
    """ADR 045 item 11: trocar a pessoa de uma compra sem parte paga é edição comum (versão 2)."""
    csrf, cartao, _ = cenario(client, usuario)
    b = nova_pessoa(client, csrf, "Pessoa B")
    c = nova_pessoa(client, csrf, "Pessoa C")
    compra = comprar(client, csrf, cartao, data=DATA_C1, parcelas=1, pessoa_id=b).json()
    corpo = {
        "tipo": "credito",
        "data": DATA_C1,
        "valor": "100.00",
        "parcelas": 1,
        "conta_id": cartao,
        "pessoa_id": c,
        "versao": 1,
    }
    r = client.put(f"/api/lancamentos/{compra['transacao_id']}", json=corpo, headers=escrita(csrf))
    assert r.status_code == 200 and (r.json()["versao"], r.json()["pessoa_id"]) == (2, c)
    assert (situacao(client, b)["divida"], situacao(client, c)["divida"]) == ("0.00", "100.00")


# ------------------------------------------------------------------ isolamento, CSRF, texto, log


def test_isolamento_entre_usuarios(
    client: TestClient, usuario: Usuario, outro_usuario: Usuario
) -> None:
    """SPEC-007-AC-6 e AC-11, INV-13: pessoa de outro usuário é 404 em toda rota e em compra e
    repasse; o user_id do corpo e da query é ignorado."""
    csrf, cartao, corrente = cenario(client, usuario)
    b = nova_pessoa(client, csrf, "Pessoa B")
    assert comprar(client, csrf, cartao, data=DATA_C1, parcelas=1, pessoa_id=b).status_code == 201

    client.cookies.clear()
    csrf_o = logar(client, outro_usuario)
    cartao_o = criar_cartao(client, csrf_o, criar_linha(client, csrf_o))
    corrente_o = criar_conta(client, csrf_o, "Corrente")
    assert client.get("/api/pessoas").json() == []
    assert client.get(f"/api/pessoas?user_id={usuario.user_id}").json() == []
    assert client.get("/api/pessoas/a-receber").json() == []
    assert client.get(f"/api/pessoas/{b}").status_code == 404
    assert client.get(f"/api/pessoas/{b}/a-receber").status_code == 404
    r = client.put(f"/api/pessoas/{b}", json={"nome": "X", "versao": 1}, headers=escrita(csrf_o))
    assert r.status_code == 404 and r.headers["X-Abako-Erro"] == "AB404"
    r = client.delete(f"/api/pessoas/{b}", params={"versao": 1}, headers=escrita(csrf_o))
    assert r.status_code == 404
    r = comprar(client, csrf_o, cartao_o, data=DATA_C1, parcelas=1, pessoa_id=b)
    assert r.status_code == 404 and r.headers["X-Abako-Erro"] == "AB404", r.text
    r = repassar(client, csrf_o, corrente_o, b, "10.00", "repasse-0001")
    assert r.status_code == 404 and r.headers["X-Abako-Erro"] == "AB404", r.text
    assert client.get("/api/lancamentos").json() == []
    # user_id no corpo é ignorado: a pessoa nasce para quem está na sessão.
    r = client.post(
        "/api/pessoas",
        json={"nome": "Pessoa B", "user_id": usuario.user_id},
        headers=escrita(csrf_o),
    )
    assert r.status_code == 201  # o mesmo nome em outro usuário não conflita
    assert len(client.get("/api/pessoas").json()) == 1

    client.cookies.clear()
    logar(client, usuario)
    assert [p["nome"] for p in client.get("/api/pessoas").json()] == ["Pessoa B"]
    assert situacao(client, b)["divida"] == "100.00"
    assert saldo(client, corrente, "2026-03-31") == "0.00"


def test_escritas_de_pessoa_exigem_csrf_e_sessao(client: TestClient, usuario: Usuario) -> None:
    csrf = logar(client, usuario)
    b = nova_pessoa(client, csrf, "Pessoa B")
    assert client.post("/api/pessoas", json={"nome": "Z"}, headers=ORIGEM).status_code == 403
    r = client.put(f"/api/pessoas/{b}", json={"nome": "Z", "versao": 1}, headers=ORIGEM)
    assert r.status_code == 403
    r = client.delete(f"/api/pessoas/{b}", params={"versao": 1}, headers=ORIGEM)
    assert r.status_code == 403
    assert len(client.get("/api/pessoas").json()) == 1

    client.cookies.clear()
    for url in ("/api/pessoas", "/api/pessoas/a-receber", f"/api/pessoas/{b}"):
        assert client.get(url).status_code == 401, url


def test_valores_de_terceiros_sao_texto_com_duas_casas(
    client: TestClient, usuario: Usuario
) -> None:
    """SPEC-007-AC-11, INV-14: a receber, fatura (total, própria, terceiros) e itens são texto."""
    csrf, cartao, corrente = cenario(client, usuario)
    b = nova_pessoa(client, csrf, "Pessoa B")
    comprar(client, csrf, cartao, data=DATA_C1, valor="10", parcelas=3, pessoa_id=b)
    repassar(client, csrf, corrente, b, "1", "repasse-0001")
    linha = a_receber(client)[b]
    for campo in ("divida", "repassado", "a_receber", "credito_da_pessoa"):
        assert isinstance(linha[campo], str), campo
    assert (linha["divida"], linha["repassado"], linha["a_receber"]) == ("10.00", "1.00", "9.00")
    f = fatura(client, cartao, C1)
    for campo in ("total", "propria", "terceiros"):
        assert isinstance(f[campo], str), campo
    assert all(isinstance(i["valor"], str) for i in f["itens"])
    assert (f["total"], f["itens"][0]["valor"]) == ("3.33", "3.33")


def test_nome_da_pessoa_fora_de_log_e_de_erro(
    client: TestClient, usuario: Usuario, caplog: pytest.LogCaptureFixture
) -> None:
    """SPEC-007-AC-11 e AC-7: nem log nem corpo de erro trazem o nome (nome repetido, longo,
    versão velha, exclusão recusada, pessoa alheia)."""
    nome = "Zelindo-Confidencial-Qwx"
    longo = nome + "x" * 80
    erros: list[str] = []
    with caplog.at_level(logging.DEBUG):
        csrf, cartao, corrente = cenario(client, usuario)
        b = nova_pessoa(client, csrf, nome)
        comprar(client, csrf, cartao, data=DATA_C1, parcelas=1, pessoa_id=b)
        repassar(client, csrf, corrente, b, "5.00", "repasse-0001")
        tentativas = [
            client.post("/api/pessoas", json={"nome": nome.upper()}, headers=escrita(csrf)),
            client.post("/api/pessoas", json={"nome": longo}, headers=escrita(csrf)),
            client.put(
                f"/api/pessoas/{b}", json={"nome": nome, "versao": 9}, headers=escrita(csrf)
            ),
            client.delete(f"/api/pessoas/{b}", params={"versao": 1}, headers=escrita(csrf)),
            client.put(
                "/api/pessoas/999999999", json={"nome": nome, "versao": 1}, headers=escrita(csrf)
            ),
            client.post(
                "/api/lancamentos",
                json={"chave": "x-12345678", "tipo": "credito", "divisao": [nome]},
                headers=escrita(csrf),
            ),
        ]
        for r in tentativas:
            assert 400 <= r.status_code < 500
            erros.append(r.text + str(dict(r.headers)))
        client.get("/api/pessoas/a-receber")
    registro = "\n".join(
        f"{rec.getMessage()} {rec.args!r} {rec.exc_text or ''}" for rec in caplog.records
    )
    assert caplog.records  # o teste capturou algo
    assert nome not in registro and nome.upper() not in registro
    for texto in erros:
        assert nome.lower() not in texto.lower()


def test_chave_desconhecida_no_corpo_e_422_e_nada_e_gravado(
    client: TestClient, usuario: Usuario
) -> None:
    """INV-32: qualquer chave fora do contrato (mesmo fora da lista de divisão) é 422 e nada é
    gravado; o 422 não ecoa o valor; `user_id` no corpo segue ignorado, a sessão manda."""
    csrf, cartao, _ = cenario(client, usuario)
    b = nova_pessoa(client, csrf, "Pessoa B")
    base = {
        "chave": "compra-0001",
        "tipo": "credito",
        "data": DATA_C1,
        "valor": "100.00",
        "parcelas": 1,
        "conta_id": cartao,
    }
    parte = [{"pessoa_id": b, "valor": "40.00"}]
    extras: list[dict[str, Any]] = [
        {"valor_terceiro": "40.00", "terceiros": parte},
        {"valor_terceiro": "40.00"},
        {"terceiros": parte},
        {"Divisao": parte},
        {"DIVISAO": parte},
        {"parte_terceiro": "40.00"},
        {"qualquer_coisa": 1},
    ]
    for extra in extras:
        r = client.post("/api/lancamentos", json=base | extra, headers=escrita(csrf))
        assert r.status_code == 422, (extra, r.text)
        assert "40.00" not in r.text, extra  # sem eco do valor recebido
        assert client.get("/api/lancamentos").json() == [], extra
    assert a_receber(client)[b]["divida"] == "0.00"
    # A edição (PUT) tem a mesma regra.
    ok = client.post("/api/lancamentos", json=base, headers=escrita(csrf))
    assert ok.status_code == 201, ok.text
    edicao = {k: v for k, v in base.items() if k != "chave"} | {"versao": 1}
    r = client.put(
        f"/api/lancamentos/{ok.json()['transacao_id']}",
        json=edicao | {"terceiros": parte},
        headers=escrita(csrf),
    )
    assert r.status_code == 422, r.text
    assert client.get(f"/api/lancamentos/{ok.json()['transacao_id']}").json()["versao"] == 1

    # `user_id` no corpo é descartado (INV-13), não vira 422 nem troca o dono.
    r = client.post(
        "/api/lancamentos",
        json=base | {"chave": "compra-0002", "user_id": usuario.user_id + 1000},
        headers=escrita(csrf),
    )
    assert r.status_code == 201, r.text
    assert len(client.get("/api/lancamentos").json()) == 2


def test_versao_de_pessoa_acima_do_inteiro_do_banco_e_422(
    client: TestClient, usuario: Usuario
) -> None:
    """A `versao` é integer no banco: acima de 2**31-1 é 422, não 500; no limite chega ao banco
    e dá o conflito normal."""
    csrf = logar(client, usuario)
    b = nova_pessoa(client, csrf, "Pessoa B")
    limite = 2**31 - 1
    r = client.put(
        f"/api/pessoas/{b}", json={"nome": "X", "versao": limite + 1}, headers=escrita(csrf)
    )
    assert r.status_code == 422, r.text
    r = client.delete(f"/api/pessoas/{b}", params={"versao": limite + 1}, headers=escrita(csrf))
    assert r.status_code == 422, r.text
    r = client.put(f"/api/pessoas/{b}", json={"nome": "X", "versao": limite}, headers=escrita(csrf))
    assert r.status_code == 409 and r.headers["X-Abako-Erro"] == "AB409", r.text
    r = client.delete(f"/api/pessoas/{b}", params={"versao": limite}, headers=escrita(csrf))
    assert r.status_code == 409 and r.headers["X-Abako-Erro"] == "AB409", r.text


def test_nome_aparado_antes_do_limite_de_80(client: TestClient, usuario: Usuario) -> None:
    """Os 80 caracteres contam depois de tirar os espaços das pontas (como no banco)."""
    csrf = logar(client, usuario)
    r = client.post("/api/pessoas", json={"nome": "  " + "n" * 80 + "  "}, headers=escrita(csrf))
    assert r.status_code == 201 and r.json()["nome"] == "n" * 80, r.text
    r = client.post("/api/pessoas", json={"nome": "m" * 81}, headers=escrita(csrf))
    assert r.status_code == 422
