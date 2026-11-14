"""API do vale (VR) com bolsos, sobra com decisão e benefícios (SPEC-013, ADR 052).

Valores esperados vêm de F-VALE-01..11 (contas à mão, em `fixtures/numericos.yaml`); a alocação, o
ajuste, a sobra e o estado são do banco, a API só os repassa. Dinheiro é texto; `hoje` é a data
civil de São Paulo, injetada de forma determinística. Tudo contra o `tst` real, só pela API.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable, Iterator
from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.services import gasto_real as svc_data
from backend.services.lancamentos import Dados, hash_corpo
from tests.backend.conftest import ORIGEM, Usuario, apagar_usuarios, criar_usuario, logar
from tests.backend.util_r2_api import Cenario, escrita, hoje_em
from tests.backend.util_vale_api import marcar_vr, mes_do_vr
from tests.db.util_saldo import fixture

pytestmark = pytest.mark.banco

HOJE = "2025-06-15"


@pytest.fixture
def novo_usuario(esquema: str) -> Iterator[Callable[[], Usuario]]:
    criados: list[Usuario] = []

    def criar() -> Usuario:
        u = criar_usuario(esquema, "v")
        criados.append(u)
        return u

    yield criar
    apagar_usuarios(esquema, criados)


@pytest.fixture
def outro_usuario(esquema: str) -> Iterator[Usuario]:
    u = criar_usuario(esquema, "o")
    yield u
    apagar_usuarios(esquema, [u])


# ------------------------------------------------------------------ montagem


def situacao(client: TestClient, mes: str | None = None, hoje: str = HOJE) -> dict[str, Any]:
    with hoje_em(client, hoje):
        r = client.get("/api/vale", params={} if mes is None else {"mes": mes})
    assert r.status_code == 200, r.text
    corpo: dict[str, Any] = r.json()
    return corpo


def decidir(c: Cenario, mes: str, destino: str) -> Any:
    return c.client.put(
        "/api/vale/decisoes",
        json={"mes": mes, "destino": destino},
        headers=escrita(c.csrf),
    )


def resumo(s: dict[str, Any]) -> dict[str, Any]:
    """Alocação inicial, ajuste, efetiva, consumo e resta por bolso, mais a sobra."""
    return {
        b: {k: s[b][k] for k in ("inicial", "ajuste", "alocacao", "consumo", "resta")}
        for b in ("trabalho", "pessoal")
    } | {"sobra": s["sobra"]}


def par(s: dict[str, Any], campo: str) -> dict[str, str]:
    return {"trabalho": s["trabalho"][campo], "pessoal": s["pessoal"][campo]}


# ------------------------------------------------------------------ situação do mês


def test_situacao_sem_conta(client: TestClient, usuario: Usuario) -> None:
    """SPEC-013-AC-6/13: sem parâmetro o estado é sem_conta; tudo zerado, sem saldo nem base."""
    c = Cenario(client, usuario, saldo=None)
    c.receita("2025-06-03", "5000.00")
    s = situacao(client, "2025-06")
    assert (s["estado"], s["conta_vr_id"], s["base_trabalho"], s["saldo_total"]) == (
        "sem_conta",
        None,
        None,
        None,
    )
    assert s["mes"] == "2025-06" and s["mes_encerrado"] is False
    assert s["credito"] == s["sobra"] == "0.00" and s["destino_padrao"] == "nenhum"
    assert s["decisao_destino"] is None and s["decisao_versao"] is None
    assert par(s, "alocacao") == par(s, "resta") == {"trabalho": "0.00", "pessoal": "0.00"}
    # a receita de caixa aparece mesmo sem VR (F-VALE-05: a tela principal mostra só ela)
    assert (s["receita_caixa"], s["receita_beneficio"], s["receita_total"]) == (
        "5000.00",
        "0.00",
        "5000.00",
    )


def test_f_vale_01_alocacao_inicial(client: TestClient, usuario: Usuario) -> None:
    """SPEC-013-AC-1 (F-VALE-01): crédito 1000,00 e base 200,00 dão 200,00 e 800,00."""
    f = fixture("F-VALE-01")
    c = Cenario(client, usuario, saldo=None)
    vr = marcar_vr(c, f["entrada"]["base_trabalho"])
    mes_do_vr(c, vr, "2025-06", f["entrada"]["credito_mes"])
    s = situacao(client, "2025-06")
    assert (s["estado"], s["conta_vr_id"], s["base_trabalho"]) == ("ok", vr, "200.00")
    assert par(s, "inicial") == f["esperado"]
    assert par(s, "alocacao") == f["esperado"]  # sem decisão, sem ajuste
    assert par(s, "ajuste") == {"trabalho": "0.00", "pessoal": "0.00"}
    assert s["credito"] == "1000.00" and s["mes_encerrado"] is False


def test_f_vale_02_sobra(client: TestClient, usuario: Usuario) -> None:
    """SPEC-013-AC-2 (F-VALE-02): consumo 150/700 deixa resta 50/100 e sobra 150,00."""
    f = fixture("F-VALE-02")
    c = Cenario(client, usuario, saldo=None)
    vr = marcar_vr(c, f["entrada"]["base_trabalho"])
    k = f["entrada"]["consumo"]
    mes_do_vr(c, vr, "2025-06", f["entrada"]["credito_mes"], k["trabalho"], k["pessoal"])
    s = situacao(client, "2025-06")
    assert par(s, "resta") == f["esperado"]["resta"]
    assert par(s, "consumo") == k
    assert s["sobra"] == f["esperado"]["sobra"]


def test_f_vale_03_estouro_nao_compensado(client: TestClient, usuario: Usuario) -> None:
    """SPEC-013-AC-2 (F-VALE-03): resta -50/100; a sobra é 100,00, sem compensar o estouro."""
    f = fixture("F-VALE-03")
    c = Cenario(client, usuario, saldo=None)
    vr = marcar_vr(c, f["entrada"]["base_trabalho"])
    k = f["entrada"]["consumo"]
    mes_do_vr(c, vr, "2025-06", f["entrada"]["credito_mes"], k["trabalho"], k["pessoal"])
    s = situacao(client, "2025-06")
    assert par(s, "resta") == f["esperado"]["resta"]
    assert s["sobra"] == f["esperado"]["sobra"] == "100.00"


def test_f_vale_06_credito_menor_igual_e_sem_credito(
    client: TestClient, novo_usuario: Callable[[], Usuario]
) -> None:
    """SPEC-013-AC-1/9 (F-VALE-06): min/max da alocação inicial e o estado sem_credito."""
    for caso in fixture("F-VALE-06")["casos"]:
        client.cookies.clear()
        c = Cenario(client, novo_usuario(), saldo=None)
        e = caso["entrada"]
        vr = marcar_vr(c, e["base_trabalho"])
        mes_do_vr(c, vr, "2025-06", e["credito"], e["consumo"]["trabalho"], e["consumo"]["pessoal"])
        s = situacao(client, "2025-06")
        x = caso["esperado"]
        assert s["estado"] == x["estado"], caso["nome"]
        assert par(s, "inicial") == x["alocacao_inicial"], caso["nome"]
        assert par(s, "resta") == x["resta"], caso["nome"]
        assert s["sobra"] == x["sobra"], caso["nome"]


def test_f_vale_07_encadeamento_de_quatro_meses(client: TestClient, usuario: Usuario) -> None:
    """SPEC-013-AC-1 (F-VALE-07): o ajuste é só a sobra decidida do mês anterior; nada acumula."""
    f = fixture("F-VALE-07")
    c = Cenario(client, usuario, saldo=None)
    vr = marcar_vr(c, f["entrada"]["base_trabalho"])
    for mes, m in f["entrada"]["meses"].items():
        mes_do_vr(c, vr, mes, m["credito"], m["consumo"]["trabalho"], m["consumo"]["pessoal"])
    for mes, m in f["entrada"]["meses"].items():
        if "decisao" in m:
            r = decidir(c, mes, m["decisao"])
            assert r.status_code == 200 and r.json()["versao"] == 1, r.text
    for mes, e in f["esperado"].items():
        s = situacao(client, mes, "2025-06-15")
        assert par(s, "ajuste") == e["ajuste"], mes
        assert par(s, "alocacao") == e["alocacao"], mes
        assert par(s, "resta") == e["resta"], mes
        assert s["sobra"] == e["sobra"], mes
        assert s["mes_encerrado"] is True


def test_f_vale_04_decisao_soma_no_mes_seguinte(client: TestClient, usuario: Usuario) -> None:
    """SPEC-013-AC-2 (F-VALE-04): decisão pessoal da sobra 150,00 dá 200/950; sem ela, 200/800."""
    f = fixture("F-VALE-04")
    c = Cenario(client, usuario, saldo=None)
    vr = marcar_vr(c, f["entrada"]["mes_1"]["base_trabalho"])
    mes_do_vr(c, vr, "2025-01", "1000.00", "150.00", "700.00")  # sobra 150,00 (F-VALE-02)
    mes_do_vr(c, vr, "2025-02", f["entrada"]["mes_2"]["credito"])
    assert (
        par(situacao(client, "2025-02"), "alocacao") == f["variante_sem_decisao"]["alocacao_mes_2"]
    )
    assert decidir(c, "2025-01", f["entrada"]["mes_1"]["decisao"]).status_code == 200
    assert par(situacao(client, "2025-02"), "alocacao") == f["esperado"]["alocacao_mes_2"]


def test_f_vale_10_decisao_substituida_e_nao_move_saldo(
    client: TestClient, usuario: Usuario
) -> None:
    """SPEC-013-AC-2/3/8 (F-VALE-10): cada decisão é versão nova que substitui a anterior; o
    histórico guarda as 3; repetir o destino vigente não cria versão; saldo e lançamentos
    ficam intactos."""
    f = fixture("F-VALE-10")
    c = Cenario(client, usuario, saldo=None)
    vr = marcar_vr(c, f["entrada"]["base_trabalho"])
    k = f["entrada"]["mes_1"]["consumo"]
    mes_do_vr(c, vr, "2025-01", f["entrada"]["mes_1"]["credito"], k["trabalho"], k["pessoal"])
    mes_do_vr(c, vr, "2025-02", f["entrada"]["mes_2"]["credito"])
    antes = situacao(client, "2025-01")
    lancamentos = client.get("/api/lancamentos").json()
    assert antes["sobra"] == f["esperado"]["sobra_mes_1"]
    assert antes["decisao_destino"] is None

    for versao, (destino, aloc) in enumerate(
        zip(f["entrada"]["decisoes_sobre_mes_1"], f["esperado"]["alocacao_mes_2"], strict=True),
        start=1,
    ):
        r = decidir(c, "2025-01", destino)
        assert r.status_code == 200, r.text
        assert r.json() == {"mes": "2025-01", "destino": destino, "versao": versao}
        assert par(situacao(client, "2025-02"), "alocacao") == aloc
        s1 = situacao(client, "2025-01")
        assert (s1["decisao_destino"], s1["decisao_versao"]) == (destino, versao)
        assert s1["saldo_total"] == antes["saldo_total"]  # a decisão nunca move saldo
    assert client.get("/api/lancamentos").json() == lancamentos

    # repetir o destino vigente (nenhum) devolve a mesma versão, sem criar outra
    assert decidir(c, "2025-01", "nenhum").json()["versao"] == f["esperado"]["versoes"]
    historico = client.get("/api/vale/decisoes").json()
    assert [(h["mes"], h["destino"], h["versao"], h["vigente"]) for h in historico] == [
        ("2025-01-01", "pessoal", 1, False),
        ("2025-01-01", "trabalho", 2, False),
        ("2025-01-01", "nenhum", 3, True),
    ]
    assert client.get("/api/vale/decisoes", params={"mes": "2025-02"}).json() == []
    assert len(client.get("/api/vale/decisoes", params={"mes": "2025-01"}).json()) == 3


def test_f_vale_05_e_09_saldo_receita_total_e_beneficios(
    client: TestClient, usuario: Usuario
) -> None:
    """SPEC-013-AC-3/4/7 (F-VALE-05 e F-VALE-09): saldo do VR acumula (250,00), receita total =
    caixa + VR + VA = 6400,00, o VA entra em /beneficios sem marca, e ambos ficam fora do gasto."""
    f = fixture("F-VALE-09")
    e = f["entrada"]
    c = Cenario(client, usuario, saldo=None)
    c.receita("2025-04-03", e["receita_caixa"])
    vr = marcar_vr(c, "200.00", desde="2025-01-01")
    c.snapshot(vr, e["vr"]["snapshot"], "2025-03-31")
    k = e["vr"]["consumo"]
    mes_do_vr(c, vr, "2025-04", e["vr"]["receita"], k["trabalho"], k["pessoal"])
    va = c.conta("VA", "beneficio")
    c.snapshot(va, e["va"]["snapshot"], "2025-03-31")
    c.receita("2025-04-06", e["va"]["receita"], conta=va)
    c.debito("2025-04-12", e["va"]["despesa"], conta=va)

    s = situacao(client, "2025-04", e["hoje"])
    x = f["esperado"]
    assert s["saldo_total"] == x["saldo_vr"]
    assert (s["receita_caixa"], s["receita_beneficio"], s["receita_total"]) == (
        x["receita_caixa"],
        x["receita_beneficio"],
        x["receita_total"],
    )
    with hoje_em(client, e["hoje"]):
        r = client.get("/api/vale/beneficios", params={"mes": "2025-04"})
    assert r.status_code == 200, r.text
    assert r.json() == {
        "mes": "2025-04",
        "itens": [
            {
                "conta_id": vr,
                "vale_refeicao": True,
                "receita_mes": "1000.00",
                "despesa_mes": "850.00",
                "saldo_total": x["saldo_vr"],
            },
            {
                "conta_id": va,
                "vale_refeicao": False,
                "receita_mes": "400.00",
                "despesa_mes": "120.00",
                "saldo_total": x["saldo_va"],
            },
        ],
    }
    gasto = client.get("/api/gasto-real", params={"mes": "2025-04"}).json()
    assert gasto["total"] == x["gasto_real"]


# ------------------------------------------------------------------ hoje determinístico


@pytest.mark.parametrize(
    ("mes", "hoje", "encerrado"),
    [
        ("2025-01", "2025-01-31", False),
        ("2025-01", "2025-02-01", True),
        ("2025-12", "2025-12-31", False),
        ("2025-12", "2026-01-01", True),
        ("2026-02", "2026-01-31", False),  # mês futuro nunca está encerrado
    ],
)
def test_mes_encerrado_na_virada_de_mes_e_de_ano(
    client: TestClient, usuario: Usuario, mes: str, hoje: str, encerrado: bool
) -> None:
    logar(client, usuario)
    assert situacao(client, mes, hoje)["mes_encerrado"] is encerrado


@pytest.mark.parametrize(("hoje", "mes"), [("2025-12-31", "2025-12"), ("2026-01-01", "2026-01")])
def test_mes_padrao_e_o_do_hoje_injetado(
    client: TestClient, usuario: Usuario, hoje: str, mes: str
) -> None:
    logar(client, usuario)
    assert situacao(client, None, hoje)["mes"] == mes
    with hoje_em(client, hoje):
        assert client.get("/api/vale/beneficios").json()["mes"] == mes


@pytest.mark.parametrize(
    ("utc", "esperado_mes"),
    [
        (datetime(2027, 1, 1, 2, 30, tzinfo=UTC), "2026-12"),  # 23:30 em São Paulo
        (datetime(2027, 1, 1, 3, 30, tzinfo=UTC), "2027-01"),  # 00:30 em São Paulo
    ],
)
def test_mes_padrao_usa_o_fuso_de_sao_paulo(
    client: TestClient,
    usuario: Usuario,
    monkeypatch: pytest.MonkeyPatch,
    utc: datetime,
    esperado_mes: str,
) -> None:
    """O caminho de produção (sem override) decide o mês corrente pela data civil de SP."""
    logar(client, usuario)

    class RelogioFalso(datetime):
        @classmethod
        def now(cls, tz: Any = None) -> RelogioFalso:
            return cls.fromtimestamp(utc.timestamp(), tz)

    monkeypatch.setattr(svc_data, "datetime", RelogioFalso)
    r = client.get("/api/vale")
    assert r.status_code == 200, r.text
    assert r.json()["mes"] == esperado_mes


def test_hoje_e_user_id_do_cliente_sao_ignorados(client: TestClient, usuario: Usuario) -> None:
    logar(client, usuario)
    base = situacao(client, "2025-06")
    with hoje_em(client, HOJE):
        r = client.get("/api/vale", params={"mes": "2025-06", "hoje": "2000-01-01", "user_id": 9})
    assert r.status_code == 200 and r.json() == base


# ------------------------------------------------------------------ decisão: regras


def test_decisao_so_em_mes_encerrado_e_com_vr(client: TestClient, usuario: Usuario) -> None:
    """SPEC-013-AC-8: mês corrente, futuro, sem VR e destino inválido são 422/AB422 literais."""
    c = Cenario(client, usuario, saldo=None)
    assert decidir(c, "2025-01", "pessoal").status_code == 422  # ainda sem VR
    marcar_vr(c)
    atual = svc_data.hoje_civil().strftime("%Y-%m")
    for mes, trecho in ((atual, "mês encerrado"), ("2099-01", "mês encerrado")):
        r = decidir(c, mes, "pessoal")
        assert r.status_code == 422 and r.headers["X-Abako-Erro"] == "AB422", mes
        assert trecho in r.json()["detail"]
    r = decidir(c, "2025-01", "tanto-faz")
    assert r.status_code == 422 and r.headers["X-Abako-Erro"] == "AB422"
    assert "trabalho, pessoal ou nenhum" in r.json()["detail"]
    # antes da vigência do parâmetro não há VR no mês
    r = decidir(c, "2024-12", "pessoal")
    assert r.status_code == 422 and "conta de vale" in r.json()["detail"]
    assert client.get("/api/vale/decisoes").json() == []


@pytest.mark.parametrize("mes", ["2025-1x", "janeiro", "", "2025-01\u0000", "2025-01" + "0" * 30])
def test_decisao_mes_invalido_e_422_nunca_500(
    client: TestClient, usuario: Usuario, mes: str
) -> None:
    c = Cenario(client, usuario, saldo=None)
    marcar_vr(c)
    assert decidir(c, mes, "pessoal").status_code == 422, repr(mes)
    with hoje_em(client, HOJE):
        r = client.get("/api/vale", params={"mes": mes})
    assert r.status_code == 422, repr(mes)


def test_leituras_com_mes_invalido_sao_ab422(client: TestClient, usuario: Usuario) -> None:
    logar(client, usuario)
    for rota in ("/api/vale", "/api/vale/beneficios", "/api/vale/parametro", "/api/vale/decisoes"):
        with hoje_em(client, HOJE):
            r = client.get(rota, params={"mes": "2025-13"})
        assert r.status_code == 422 and r.headers["X-Abako-Erro"] == "AB422", rota
        assert r.json()["detail"] == "o mês precisa estar no formato AAAA-MM", rota


# ------------------------------------------------------------------ parâmetro


def test_parametro_grava_le_e_e_idempotente(client: TestClient, usuario: Usuario) -> None:
    """SPEC-013-AC-6/9: a conta e a base valem a partir da vigência; repetir não muda nada; uma
    nova base vale a partir do mês escolhido e os anteriores mantêm a antiga."""
    c = Cenario(client, usuario, saldo=None)
    with hoje_em(client, HOJE):
        assert client.get("/api/vale/parametro").json() is None
    vr = marcar_vr(c, "200", "pessoal", "2025-01-01")
    esperado = {
        "conta_id": vr,
        "base_trabalho": "200.00",
        "destino_padrao": "pessoal",
        "vigente_desde": "2025-01-01",
    }
    with hoje_em(client, HOJE):
        assert client.get("/api/vale/parametro").json() == esperado
        assert client.get("/api/vale/parametro", params={"mes": "2024-12"}).json() is None
    corpo = {**esperado, "base_trabalho": "200.00"}
    for _ in range(2):  # idempotente
        r = client.put("/api/vale/parametro", json=corpo, headers=escrita(c.csrf))
        assert r.status_code == 200 and r.json() == esperado
    mes_do_vr(c, vr, "2025-02", "1000.00")
    mes_do_vr(c, vr, "2025-03", "1000.00")
    nova = {**corpo, "base_trabalho": "300.00", "vigente_desde": "2025-03-01"}
    assert client.put("/api/vale/parametro", json=nova, headers=escrita(c.csrf)).status_code == 200
    antigos = situacao(client, "2025-02")
    novos = situacao(client, "2025-03")
    assert (antigos["base_trabalho"], par(antigos, "inicial")) == (
        "200.00",
        {"trabalho": "200.00", "pessoal": "800.00"},
    )
    assert (novos["base_trabalho"], par(novos, "inicial")) == (
        "300.00",
        {"trabalho": "300.00", "pessoal": "700.00"},
    )
    assert situacao(client, "2025-02")["destino_padrao"] == "pessoal"


def test_parametro_recusas(client: TestClient, usuario: Usuario, outro_usuario: Usuario) -> None:
    """SPEC-013-AC-6/11/13: conta que não é de benefício, de outro usuário, vigência fora do dia 1,
    destino e base inválidos, e chave desconhecida são 422/404; o 422 não ecoa o que veio."""
    c = Cenario(client, usuario, saldo=None)
    vr = c.conta("VR", "beneficio")
    base = {
        "conta_id": vr,
        "base_trabalho": "200.00",
        "destino_padrao": "nenhum",
        "vigente_desde": "2025-01-01",
    }

    def gravar(**mudancas: Any) -> Any:
        return client.put("/api/vale/parametro", json={**base, **mudancas}, headers=escrita(c.csrf))

    r = gravar(conta_id=c.corrente)
    assert r.status_code == 422 and r.headers["X-Abako-Erro"] == "AB422"
    assert r.json()["detail"] == "a conta do vale precisa ser de benefício"
    r = gravar(conta_id=vr + 10_000_000)
    assert r.status_code == 404 and r.headers["X-Abako-Erro"] == "AB404"
    r = gravar(vigente_desde="2025-01-15")
    assert r.status_code == 422 and r.headers["X-Abako-Erro"] == "AB422"
    r = gravar(destino_padrao="outro")
    assert r.status_code == 422 and r.headers["X-Abako-Erro"] == "AB422"
    for base_ruim in ("-1", "200.001", "abc", ""):
        assert gravar(base_trabalho=base_ruim).status_code == 422, base_ruim
    for conta_ruim in (0, -1, 2**63):
        assert gravar(conta_id=conta_ruim).status_code == 422, conta_ruim
    r = gravar(destino_padrao="X" * 40)
    assert r.status_code == 422 and "XXXX" not in r.text
    r = gravar(destino_padrao="a\u0000b")
    assert r.status_code == 422
    r = client.put(
        "/api/vale/parametro",
        json={**base, "campo_estranho_ZZ": "valor-sigiloso-QQ"},
        headers=escrita(c.csrf),
    )
    assert r.status_code == 422 and "valor-sigiloso-QQ" not in r.text
    assert client.get("/api/vale/decisoes").json() == []

    # a conta de outro usuário é 404, e `user_id` no corpo é descartado (a sessão manda)
    client.post("/api/auth/logout", headers=escrita(c.csrf))
    client.cookies.clear()
    c2 = Cenario(client, outro_usuario, saldo=None)
    r = client.put(
        "/api/vale/parametro",
        json={**base, "user_id": usuario.user_id},
        headers=escrita(c2.csrf),
    )
    assert r.status_code == 404 and r.headers["X-Abako-Erro"] == "AB404"
    meu_vr = c2.conta("VR2", "beneficio")
    r = client.put(
        "/api/vale/parametro",
        json={**base, "conta_id": meu_vr, "user_id": usuario.user_id},
        headers=escrita(c2.csrf),
    )
    assert r.status_code == 200 and r.json()["conta_id"] == meu_vr


def test_parametro_recusa_despesa_sem_bolso(client: TestClient, usuario: Usuario) -> None:
    """SPEC-013-AC-6: despesa da conta a partir da vigência sem bolso: o usuário a edita antes."""
    c = Cenario(client, usuario, saldo=None)
    conta = c.conta("VR", "beneficio")
    c.debito("2025-02-03", "40.00", conta=conta)
    r = client.put(
        "/api/vale/parametro",
        json={
            "conta_id": conta,
            "base_trabalho": "200.00",
            "destino_padrao": "nenhum",
            "vigente_desde": "2025-01-01",
        },
        headers=escrita(c.csrf),
    )
    assert r.status_code == 422 and r.headers["X-Abako-Erro"] == "AB422"
    assert (
        r.json()["detail"]
        == "edite as despesas antigas da conta informando o bolso antes de marcá-la como VR"
    )


# ------------------------------------------------------------------ bolso no lançamento


def test_bolso_obrigatorio_no_vr_e_proibido_fora(client: TestClient, usuario: Usuario) -> None:
    """SPEC-013-AC-7/10/13: a despesa no VR exige bolso; fora do VR (corrente, VA, receita) o
    bolso é recusado pelo banco; bolso fora de trabalho|pessoal é 422."""
    c = Cenario(client, usuario, saldo=None)
    vr = marcar_vr(c)
    va = c.conta("VA", "beneficio")

    def lancar(**campos: Any) -> Any:
        corpo = {"tipo": "debito", "data": "2025-06-02", "valor": "10.00", **campos}
        return client.post("/api/lancamentos", json=corpo, headers=escrita(c.csrf))

    r = lancar(chave="chave-vr-0001", conta_id=vr)
    assert r.status_code == 422 and r.headers["X-Abako-Erro"] == "AB422"
    assert r.json()["detail"] == "a despesa do vale precisa de bolso: trabalho ou pessoal"
    r = lancar(chave="chave-vr-0002", conta_id=vr, bolso="pessoal")
    assert r.status_code == 201 and r.json()["bolso"] == "pessoal", r.text
    for conta, extra in ((c.corrente, {}), (va, {}), (vr, {"tipo": "receita"})):
        r = lancar(
            chave=f"chave-fora-{conta}-{extra.get('tipo', 'd')}",
            conta_id=conta,
            bolso="trabalho",
            **extra,
        )
        assert r.status_code == 422 and r.headers["X-Abako-Erro"] == "AB422", (conta, extra)
        assert r.json()["detail"] == (
            "bolso só na despesa da conta do vale ou de conta de benefício sem vale marcado"
        )
    assert lancar(chave="chave-fora-ok-01", conta_id=va).json()["bolso"] is None
    r = lancar(chave="chave-vr-0003", conta_id=vr, bolso="outro")
    assert r.status_code == 422 and "outro" not in r.text
    # antes da vigência do parâmetro nenhum VR estava marcado: a conta de benefício aceita o bolso
    # de forma opcional (classificar antes de marcar), nunca obrigatória
    r = lancar(chave="chave-vr-0004", conta_id=vr, data="2024-12-20")
    assert r.status_code == 201 and r.json()["bolso"] is None
    r = lancar(chave="chave-vr-0005", conta_id=vr, data="2024-12-20", bolso="pessoal")
    assert r.status_code == 201 and r.json()["bolso"] == "pessoal", r.text


def test_conta_de_beneficio_sem_vr_aceita_bolso_opcional(
    client: TestClient, usuario: Usuario
) -> None:
    """SPEC-013-AC-10: sem VR marcado, a despesa de conta de benefício aceita bolso (opcional);
    conta comum e receita continuam recusando; a API só repassa o bolso, o banco decide."""
    c = Cenario(client, usuario, saldo=None)
    conta = c.conta("Beneficio", "beneficio")

    def lancar(**campos: Any) -> Any:
        corpo = {"tipo": "debito", "data": "2025-06-02", "valor": "10.00", **campos}
        return client.post("/api/lancamentos", json=corpo, headers=escrita(c.csrf))

    com = lancar(chave="chave-opc-0001", conta_id=conta, bolso="trabalho")
    assert com.status_code == 201 and com.json()["bolso"] == "trabalho", com.text
    sem = lancar(chave="chave-opc-0002", conta_id=conta)
    assert sem.status_code == 201 and sem.json()["bolso"] is None, sem.text
    for chave, campos in (
        ("chave-opc-0003", {"conta_id": c.corrente}),
        ("chave-opc-0004", {"conta_id": conta, "tipo": "receita"}),
    ):
        r = lancar(chave=chave, bolso="pessoal", **campos)
        assert r.status_code == 422 and r.headers["X-Abako-Erro"] == "AB422", campos


def test_classificar_antes_e_marcar_o_vr_da_situacao_correta(
    client: TestClient, usuario: Usuario
) -> None:
    """SPEC-013-AC-10: classificar as despesas antes, marcar o VR e ver a situação do mês: o
    consumo por bolso já sai das despesas classificadas (crédito 1000,00, base 200,00)."""
    c = Cenario(client, usuario, saldo=None)
    conta = c.conta("Beneficio", "beneficio")
    c.receita("2025-06-05", "1000.00", conta=conta)
    c.lancar(tipo="debito", data="2025-06-10", valor="100.00", conta_id=conta, bolso="trabalho")
    c.lancar(tipo="debito", data="2025-06-11", valor="30.00", conta_id=conta, bolso="pessoal")
    r = client.put(
        "/api/vale/parametro",
        json={
            "conta_id": conta,
            "base_trabalho": "200.00",
            "destino_padrao": "nenhum",
            "vigente_desde": "2025-01-01",
        },
        headers=escrita(c.csrf),
    )
    assert r.status_code == 200, r.text
    s = situacao(client, "2025-06")
    assert s["estado"] == "ok" and s["credito"] == "1000.00"
    assert par(s, "consumo") == {"trabalho": "100.00", "pessoal": "30.00"}
    assert par(s, "resta") == {"trabalho": "100.00", "pessoal": "770.00"}


def test_edicao_e_exclusao_acompanham_o_bolso(client: TestClient, usuario: Usuario) -> None:
    """SPEC-013-AC-10: a edição exige o bolso de novo e vale a versão vigente; a exclusão lógica
    tira o consumo; a listagem e a leitura trazem o bolso."""
    c = Cenario(client, usuario, saldo=None)
    vr = marcar_vr(c)
    mes_do_vr(c, vr, "2025-06", "1000.00")
    d = c.lancar(tipo="debito", data="2025-06-10", valor="100.00", conta_id=vr, bolso="trabalho")
    assert d["bolso"] == "trabalho"
    assert par(situacao(client, "2025-06"), "consumo") == {"trabalho": "100.00", "pessoal": "0.00"}

    corpo = {
        "tipo": "debito",
        "data": "2025-06-10",
        "valor": "110.00",
        "conta_id": vr,
        "versao": d["versao"],
    }
    r = client.put(f"/api/lancamentos/{d['transacao_id']}", json=corpo, headers=escrita(c.csrf))
    assert r.status_code == 422 and "bolso" in r.json()["detail"]
    r = client.put(
        f"/api/lancamentos/{d['transacao_id']}",
        json={**corpo, "bolso": "pessoal"},
        headers=escrita(c.csrf),
    )
    assert r.status_code == 200, r.text
    assert (r.json()["versao"], r.json()["bolso"]) == (d["versao"] + 1, "pessoal")
    assert par(situacao(client, "2025-06"), "consumo") == {"trabalho": "0.00", "pessoal": "110.00"}
    lido = client.get(f"/api/lancamentos/{d['transacao_id']}").json()
    assert lido["bolso"] == "pessoal"
    assert [x["bolso"] for x in client.get("/api/lancamentos", params={"conta_id": vr}).json()] == [
        "pessoal",
        None,  # a receita do crédito
    ]

    r = client.delete(
        f"/api/lancamentos/{d['transacao_id']}",
        params={"versao": r.json()["versao"]},
        headers=escrita(c.csrf),
    )
    assert r.status_code == 204
    assert par(situacao(client, "2025-06"), "consumo") == {"trabalho": "0.00", "pessoal": "0.00"}


def test_idempotencia_com_bolso(client: TestClient, usuario: Usuario) -> None:
    """SPEC-013-AC-13 (INV-28): o bolso entra no corpo da chave: repetir igual não duplica (200);
    a mesma chave com outro bolso é outro corpo (422). Sem bolso, o hash não muda."""
    c = Cenario(client, usuario, saldo=None)
    vr = marcar_vr(c)
    corpo = {
        "chave": "chave-bolso-0001",
        "tipo": "debito",
        "data": "2025-06-02",
        "valor": "10.00",
        "conta_id": vr,
        "bolso": "pessoal",
    }
    h = escrita(c.csrf)
    primeira = client.post("/api/lancamentos", json=corpo, headers=h)
    segunda = client.post("/api/lancamentos", json=corpo, headers=h)
    assert (primeira.status_code, segunda.status_code) == (201, 200)
    assert primeira.json() == segunda.json()
    outra = client.post("/api/lancamentos", json={**corpo, "bolso": "trabalho"}, headers=h)
    assert outra.status_code == 422, outra.text
    assert len(client.get("/api/lancamentos", params={"conta_id": vr}).json()) == 1
    # sem bolso, o canônico antigo (sem a chave `bolso`) continua valendo
    d = Dados("debito", date(2026, 2, 2), Decimal("50"), 3, None, None, None, None)
    antigo = (
        '{"bruto":null,"conta_destino_id":null,"conta_id":3,"data":"2026-02-02",'
        '"descricao":null,"imposto":null,"parcelas":null,"tipo":"debito","valor":"50.00"}'
    )
    assert hash_corpo(d) == hashlib.sha256(antigo.encode()).hexdigest()
    assert hash_corpo(replace(d, bolso="pessoal")) != hash_corpo(d)


# ------------------------------------------------------------------ segurança


ROTAS_GET = (
    "/api/vale",
    "/api/vale/beneficios",
    "/api/vale/parametro",
    "/api/vale/decisoes",
)
ROTAS_PUT = ("/api/vale/parametro", "/api/vale/decisoes")


def test_sem_sessao_e_401(client: TestClient) -> None:
    for rota in ROTAS_GET:
        assert client.get(rota).status_code == 401, rota
    for rota in ROTAS_PUT:
        assert client.put(rota, json={}, headers=ORIGEM).status_code == 401, rota


def test_escrita_sem_csrf_e_403(client: TestClient, usuario: Usuario) -> None:
    c = Cenario(client, usuario, saldo=None)
    vr = c.conta("VR", "beneficio")
    corpos = {
        "/api/vale/parametro": {
            "conta_id": vr,
            "base_trabalho": "200.00",
            "destino_padrao": "nenhum",
            "vigente_desde": "2025-01-01",
        },
        "/api/vale/decisoes": {"mes": "2025-01", "destino": "pessoal"},
    }
    for rota, corpo in corpos.items():
        assert client.put(rota, json=corpo, headers=ORIGEM).status_code == 403, rota
        r = client.put(rota, json=corpo, headers={**ORIGEM, "X-CSRF-Token": "errado"})
        assert r.status_code == 403, rota
    with hoje_em(client, HOJE):
        assert client.get("/api/vale/parametro").json() is None  # nada foi gravado


def test_metodos_nao_previstos_sao_405(client: TestClient, usuario: Usuario) -> None:
    c = Cenario(client, usuario, saldo=None)
    for rota in ROTAS_GET:
        for metodo in ("post", "patch", "delete"):
            r = getattr(client, metodo)(rota, headers=escrita(c.csrf))
            assert r.status_code == 405, (rota, metodo)
    for rota in ("/api/vale", "/api/vale/beneficios"):
        assert client.put(rota, json={}, headers=escrita(c.csrf)).status_code == 405, rota


def test_isolamento_entre_usuarios(
    client: TestClient, usuario: Usuario, outro_usuario: Usuario
) -> None:
    """SPEC-013-AC-11 (INV-13): o outro usuário não vê parâmetro, situação, benefícios nem decisões
    do dono, e não decide a sobra de um mês que só o dono configurou."""
    c = Cenario(client, usuario, saldo=None)
    vr = marcar_vr(c, destino="pessoal")
    mes_do_vr(c, vr, "2025-01", "1000.00", "150.00", "700.00")
    c.conta("VA", "beneficio")
    assert decidir(c, "2025-01", "pessoal").status_code == 200
    assert situacao(client, "2025-01")["sobra"] == "150.00"
    client.post("/api/auth/logout", headers=escrita(c.csrf))
    client.cookies.clear()

    c2 = Cenario(client, outro_usuario, saldo=None)
    s = situacao(client, "2025-01")
    assert (s["estado"], s["conta_vr_id"], s["credito"], s["sobra"]) == (
        "sem_conta",
        None,
        "0.00",
        "0.00",
    )
    assert s["decisao_destino"] is None and s["destino_padrao"] == "nenhum"
    with hoje_em(client, HOJE):
        assert client.get("/api/vale/beneficios").json()["itens"] == []
        assert client.get("/api/vale/parametro").json() is None
    assert client.get("/api/vale/decisoes").json() == []
    assert decidir(c2, "2025-01", "trabalho").status_code == 422  # sem VR dele


def test_valores_e_nomes_fora_do_log(
    client: TestClient, usuario: Usuario, caplog: pytest.LogCaptureFixture
) -> None:
    """SPEC-013-AC-13: nenhum valor financeiro nem nome de conta vai a log."""
    with caplog.at_level(logging.DEBUG):
        c = Cenario(client, usuario, saldo=None)
        vr = c.conta("Conta-VR-Sigilosa-ZZ", "beneficio")
        r = client.put(
            "/api/vale/parametro",
            json={
                "conta_id": vr,
                "base_trabalho": "123.45",
                "destino_padrao": "nenhum",
                "vigente_desde": "2025-01-01",
            },
            headers=escrita(c.csrf),
        )
        assert r.status_code == 200
        mes_do_vr(c, vr, "2025-06", "7654.32", "88.77", "99.66")
        s = situacao(client, "2025-06")
        client.get("/api/vale/beneficios")
        decidir(c, "2025-01", "pessoal")
    # alocação 123.45 / 7530.87; resta 34.68 / 7431.21; sobra = 34.68 + 7431.21
    assert s["sobra"] == "7465.89"
    for texto in (
        "Conta-VR-Sigilosa-ZZ",
        "7654.32",
        "123.45",
        "88.77",
        "99.66",
        "7530.87",
        "7465.89",
        "7431.21",
        "34.68",
    ):
        assert texto not in caplog.text


def test_dinheiro_sempre_em_texto(client: TestClient, usuario: Usuario) -> None:
    """SPEC-013-AC-13 (INV-14): nenhum campo monetário sai como número."""
    c = Cenario(client, usuario, saldo=None)
    vr = marcar_vr(c)
    mes_do_vr(c, vr, "2025-06", "1000.00", "10.00", "20.00")
    s = situacao(client, "2025-06")
    textos = [
        s[k]
        for k in (
            "credito",
            "base_trabalho",
            "sobra",
            "saldo_total",
            "receita_caixa",
            "receita_beneficio",
            "receita_total",
        )
    ]
    for b in ("trabalho", "pessoal"):
        textos += list(s[b].values())
    assert all(isinstance(t, str) for t in textos) and len(textos) == 17
    with hoje_em(client, HOJE):
        itens = client.get("/api/vale/beneficios").json()["itens"]
        parametro = client.get("/api/vale/parametro").json()
    assert all(
        isinstance(i[k], str) for i in itens for k in ("receita_mes", "despesa_mes", "saldo_total")
    )
    assert isinstance(parametro["base_trabalho"], str)
