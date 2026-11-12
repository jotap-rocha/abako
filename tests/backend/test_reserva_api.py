"""API da reserva (SPEC-009, ADR 047). Valores esperados vêm de F-RES-01..08 (contas à mão); o
nível, a cobertura e o aporte são do banco, a API só os repassa. Dinheiro é texto; `hoje` é a data
civil de São Paulo, injetada de forma determinística."""

from __future__ import annotations

import itertools
import logging
from collections.abc import Iterator
from datetime import UTC, date, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.routers import reserva as router_reserva
from backend.services import gasto_real as svc_data
from tests.backend.conftest import ORIGEM, Usuario, apagar_usuarios, criar_usuario, logar

pytestmark = pytest.mark.banco

_contador = itertools.count(1)


def escrita(csrf: str) -> dict[str, str]:
    return {**ORIGEM, "X-CSRF-Token": csrf}


@pytest.fixture
def outro_usuario(esquema: str) -> Iterator[Usuario]:
    u = criar_usuario(esquema, "o")
    yield u
    apagar_usuarios(esquema, [u])


class Cenario:
    """Contas, snapshots, rendimentos e parâmetros de um usuário, criados só pela API."""

    def __init__(self, client: TestClient, usuario: Usuario) -> None:
        self.client = client
        self.csrf = logar(client, usuario)
        self.corrente = self.conta("Corrente", "corrente")

    def conta(self, nome: str, tipo: str, **campos: Any) -> int:
        corpo = {"nome": nome, "tipo": tipo, "conta_beneficio": False, **campos}
        r = self.client.post("/api/contas", json=corpo, headers=escrita(self.csrf))
        assert r.status_code == 201, r.text
        conta_id: int = r.json()["conta_id"]
        return conta_id

    def reserva(
        self, nome: str, saldo: str, data: str = "2026-01-01", tipo: str = "reserva"
    ) -> int:
        extra = {"conta_mae_id": self.corrente} if tipo == "reserva" else {}
        conta_id = self.conta(nome, tipo, **extra)
        r = self.client.post(
            f"/api/contas/{conta_id}/snapshots",
            json={"data": data, "valor": saldo},
            headers=escrita(self.csrf),
        )
        assert r.status_code == 201, r.text
        return conta_id

    def rendimento(self, conta_id: int, data: str, bruto: str, imposto: str) -> dict[str, Any]:
        corpo = {
            "chave": f"chave-{next(_contador):08d}",
            "tipo": "rendimento",
            "data": data,
            "bruto": bruto,
            "imposto": imposto,
            "conta_id": conta_id,
        }
        r = self.client.post("/api/lancamentos", json=corpo, headers=escrita(self.csrf))
        assert r.status_code == 201, r.text
        saida: dict[str, Any] = r.json()
        return saida

    def excluir(self, lancamento: dict[str, Any]) -> None:
        r = self.client.delete(
            f"/api/lancamentos/{lancamento['transacao_id']}",
            params={"versao": lancamento["versao"]},
            headers=escrita(self.csrf),
        )
        assert r.status_code == 204, r.text

    def parametros(
        self,
        gasto: str,
        meses: int = 3,
        desde: str = "2026-01-01",
        alvo: str | None = None,
    ) -> dict[str, Any]:
        r = self.client.put(
            "/api/reserva/parametros",
            json={
                "meses": meses,
                "gasto_essencial": gasto,
                "data_alvo": alvo,
                "vigente_desde": desde,
            },
            headers=escrita(self.csrf),
        )
        assert r.status_code == 200, r.text
        saida: dict[str, Any] = r.json()
        return saida


def em(client: TestClient, hoje: str) -> dict[str, Any]:
    """Situação com `hoje` injetado (a rota não recebe a data do cliente)."""
    app: Any = client.app
    app.dependency_overrides[router_reserva.hoje_civil] = lambda: date.fromisoformat(hoje)
    try:
        r = client.get("/api/reserva")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200, r.text
    corpo: dict[str, Any] = r.json()
    return corpo


# ------------------------------------------------------------------ nível, falta, cobertura


@pytest.mark.parametrize(
    ("saldo", "nivel", "falta", "cobertura"),
    [
        ("3000.00", "critica", "9000.00", "0.75"),
        ("5999.99", "critica", "6000.01", "1.50"),
        ("6000.00", "atencao", "6000.00", "1.50"),
        ("11999.99", "atencao", "0.01", "3.00"),
        ("12000.00", "saudavel", "0.00", "3.00"),
    ],
)
def test_nivel_nos_cortes_de_50_e_100_por_cento_f_res_01(
    client: TestClient, usuario: Usuario, saldo: str, nivel: str, falta: str, cobertura: str
) -> None:
    """SPEC-009-AC-10 (F-RES-01): meta 3 x 4000,00 = 12000,00; os cortes de 50% e 100% valem
    exatamente, um centavo para cada lado; cobertura sobre o líquido, meio-para-cima."""
    c = Cenario(client, usuario)
    c.reserva("Reserva", saldo)
    c.parametros("4000.00")
    s = em(client, "2026-04-01")
    assert (s["nivel"], s["falta"], s["meta"]) == (nivel, falta, "12000.00")
    assert s["cobertura_meses"] == cobertura
    assert s["saldo_liquido"] == saldo and s["config_pendente"] is False


@pytest.mark.parametrize(
    ("saldo", "gasto", "cobertura"),
    [
        ("1000.00", "3000.00", "0.33"),
        ("2000.00", "3000.00", "0.67"),
        ("1.00", "200.00", "0.01"),  # empate 0,005 sobe
        ("9000.00", "3000.00", "3.00"),
    ],
)
def test_cobertura_meio_para_cima_f_res_06(
    client: TestClient, usuario: Usuario, saldo: str, gasto: str, cobertura: str
) -> None:
    """SPEC-009-AC-10 (F-RES-02, F-RES-06): cobertura em texto com 2 casas."""
    c = Cenario(client, usuario)
    c.reserva("Reserva", saldo)
    c.parametros(gasto)
    s = em(client, "2026-04-01")
    assert s["cobertura_meses"] == cobertura
    assert isinstance(s["cobertura_meses"], str)


def test_bruto_vs_liquido_f_res_03(client: TestClient, usuario: Usuario) -> None:
    """SPEC-009-AC-10 (F-RES-03): líquido 5139,50; imposto 40,50; bruto 5180,00. Cobertura (3,43)
    e nível usam o líquido. O rendimento excluído e o de conta de investimento não contam."""
    c = Cenario(client, usuario)
    reserva = c.reserva("Reserva", "5000.00")
    c.rendimento(reserva, "2026-02-10", "100.00", "22.50")
    c.rendimento(reserva, "2026-03-10", "80.00", "18.00")
    excluido = c.rendimento(reserva, "2026-02-20", "50.00", "10.00")
    c.excluir(excluido)
    invest = c.reserva("Investimento", "1000.00", tipo="investimento")
    c.rendimento(invest, "2026-03-15", "200.00", "40.00")
    c.parametros("1500.00")

    assert em(client, "2026-04-01") == {
        "contas_reserva": 1,
        "saldo_liquido": "5139.50",
        "imposto_acumulado": "40.50",
        "saldo_bruto": "5180.00",
        "meses_meta": 3,
        "gasto_essencial": "1500.00",
        "meta": "4500.00",
        "nivel": "saudavel",
        "falta": "0.00",
        "cobertura_meses": "3.43",
        "data_alvo": None,
        "meses_ate_alvo": None,
        "alvo_vencida": False,
        "aporte_mensal": None,
        "config_pendente": False,
    }


def test_soma_de_duas_reservas_f_res_04(client: TestClient, usuario: Usuario) -> None:
    """SPEC-009-AC-10 (F-RES-04): a reserva soma as duas caixinhas (6577,50; imposto 22,50;
    bruto 6600,00); o investimento fica fora; saudável sobre a soma."""
    c = Cenario(client, usuario)
    c.reserva("Caixinha A", "4000.00")
    b = c.reserva("Caixinha B", "2500.00")
    c.rendimento(b, "2026-02-10", "100.00", "22.50")
    c.reserva("Investimento", "10000.00", tipo="investimento")
    c.parametros("2000.00")
    s = em(client, "2026-04-01")
    assert (s["contas_reserva"], s["saldo_liquido"], s["imposto_acumulado"]) == (
        2,
        "6577.50",
        "22.50",
    )
    assert (s["saldo_bruto"], s["meta"], s["nivel"], s["falta"], s["cobertura_meses"]) == (
        "6600.00",
        "6000.00",
        "saudavel",
        "0.00",
        "3.29",
    )


# ------------------------------------------------------------------ aporte


@pytest.mark.parametrize(
    ("saldo", "alvo", "ate", "falta", "aporte", "vencida"),
    [
        ("3000.00", "2026-10-20", 6, "9000.00", "1500.00", False),
        ("3000.00", "2026-11-03", 7, "9000.00", "1285.72", False),  # 9000/7 = 1285,714..
        ("11000.00", "2026-07-01", 3, "1000.00", "333.34", False),  # 1000/3 = 333,333..
        ("3000.00", "2027-02-01", 10, "9000.00", "900.00", False),  # vira o ano
        ("3000.00", "2026-04-30", 1, "9000.00", "9000.00", False),  # mesmo mês: mínimo 1
        ("3000.00", "2026-03-31", None, "9000.00", None, True),  # passada: só a falta
        ("12000.00", "2026-10-20", 6, "0.00", "0.00", False),  # meta atingida
        ("3000.00", None, None, "9000.00", None, False),  # sem data-alvo
    ],
)
def test_aporte_nao_exato_e_casos_de_borda_f_res_05(
    client: TestClient,
    usuario: Usuario,
    saldo: str,
    alvo: str | None,
    ate: int | None,
    falta: str,
    aporte: str | None,
    vencida: bool,
) -> None:
    """SPEC-009-AC-10 (F-RES-05): hoje 15/04/2026, meta 12000,00; aporte arredondado para cima."""
    c = Cenario(client, usuario)
    c.reserva("Reserva", saldo)
    c.parametros("4000.00", alvo=alvo)
    s = em(client, "2026-04-15")
    assert (s["falta"], s["aporte_mensal"], s["alvo_vencida"]) == (falta, aporte, vencida)
    assert s["data_alvo"] == alvo
    if ate is not None:
        assert s["meses_ate_alvo"] == ate
    elif aporte is None:
        assert s["meses_ate_alvo"] is None


# ------------------------------------------------------------------ configuração pendente


def test_sem_parametro_e_config_pendente_f_res_07(client: TestClient, usuario: Usuario) -> None:
    """SPEC-009-AC-10 (F-RES-07): nunca informado = pendente, N=3, campos nulos, saldo devolvido."""
    c = Cenario(client, usuario)
    c.reserva("Reserva", "3000.00")
    assert em(client, "2026-04-01") == {
        "contas_reserva": 1,
        "saldo_liquido": "3000.00",
        "imposto_acumulado": "0.00",
        "saldo_bruto": "3000.00",
        "meses_meta": 3,
        "gasto_essencial": None,
        "meta": None,
        "nivel": None,
        "falta": None,
        "cobertura_meses": None,
        "data_alvo": None,
        "meses_ate_alvo": None,
        "alvo_vencida": False,
        "aporte_mensal": None,
        "config_pendente": True,
    }


def test_gasto_essencial_zero_e_config_pendente_f_res_07(
    client: TestClient, usuario: Usuario
) -> None:
    """SPEC-009-AC-10 (F-RES-07): gasto essencial zero é aceito e deixa tudo pendente."""
    c = Cenario(client, usuario)
    c.reserva("Reserva", "3000.00")
    assert c.parametros("0", alvo="2026-12-01")["gasto_essencial"] == "0.00"
    s = em(client, "2026-04-01")
    assert s["config_pendente"] is True and s["gasto_essencial"] == "0.00"
    for campo in ("cobertura_meses", "meta", "nivel", "falta", "aporte_mensal"):
        assert s[campo] is None, campo
    assert s["saldo_liquido"] == "3000.00" and s["meses_meta"] == 3


def test_usuario_sem_reserva_tem_saldo_zero(client: TestClient, usuario: Usuario) -> None:
    """SPEC-009-AC-10: sem conta de reserva a situação existe, com zeros e pendente."""
    logar(client, usuario)
    s = em(client, "2026-04-01")
    assert (s["contas_reserva"], s["saldo_liquido"], s["saldo_bruto"]) == (0, "0.00", "0.00")
    assert s["config_pendente"] is True


# ------------------------------------------------------------------ parâmetros e vigência


def test_vigencia_dos_parametros_f_res_08(client: TestClient, usuario: Usuario) -> None:
    """SPEC-009-AC-10 (F-RES-08): vale o maior `vigente_desde` <= hoje; o corte de 50% é exato;
    regravar na mesma vigência vale o último; a listagem traz uma linha por vigência."""
    c = Cenario(client, usuario)
    c.reserva("Reserva", "5000.00", data="2025-01-01")
    c.parametros("2000.00", meses=3, desde="2026-01-01")
    c.parametros("2500.00", meses=4, desde="2026-06-01")

    assert em(client, "2025-12-31")["config_pendente"] is True
    s = em(client, "2026-05-31")
    assert (s["meta"], s["nivel"], s["cobertura_meses"], s["falta"]) == (
        "6000.00",
        "atencao",
        "2.50",
        "1000.00",
    )
    s = em(client, "2026-06-01")
    assert (s["meta"], s["nivel"], s["cobertura_meses"], s["falta"], s["meses_meta"]) == (
        "10000.00",
        "atencao",
        "2.00",
        "5000.00",
        4,
    )

    c.parametros("2800.00", meses=4, desde="2026-06-01")
    s = em(client, "2026-06-01")
    assert (s["meta"], s["cobertura_meses"]) == ("11200.00", "1.79")
    assert em(client, "2026-05-31")["meta"] == "6000.00"  # a vigência anterior não mudou

    r = client.get("/api/reserva/parametros")
    assert r.status_code == 200
    assert r.json() == [
        {
            "vigente_desde": "2026-01-01",
            "meses": 3,
            "gasto_essencial": "2000.00",
            "data_alvo": None,
        },
        {
            "vigente_desde": "2026-06-01",
            "meses": 4,
            "gasto_essencial": "2800.00",
            "data_alvo": None,
        },
    ]


def test_gravar_parametro_e_idempotente(client: TestClient, usuario: Usuario) -> None:
    """SPEC-009-AC-10: repetir o mesmo parâmetro devolve o mesmo registro e não acrescenta."""
    c = Cenario(client, usuario)
    primeiro = c.parametros("1500.5", alvo="2026-12-01")
    segundo = c.parametros("1500.50", alvo="2026-12-01")
    assert (
        primeiro
        == segundo
        == {
            "vigente_desde": "2026-01-01",
            "meses": 3,
            "gasto_essencial": "1500.50",
            "data_alvo": "2026-12-01",
        }
    )
    assert len(client.get("/api/reserva/parametros").json()) == 1


def test_hoje_decide_o_aporte_na_virada_de_mes(client: TestClient, usuario: Usuario) -> None:
    """SPEC-009-AC-10: hoje determinístico; 30/04 faltam 3 meses para julho, 01/05 faltam 2."""
    c = Cenario(client, usuario)
    c.reserva("Reserva", "3000.00")
    c.parametros("4000.00", alvo="2026-07-15")
    antes = em(client, "2026-04-30")
    depois = em(client, "2026-05-01")
    assert (antes["meses_ate_alvo"], antes["aporte_mensal"]) == (3, "3000.00")
    assert (depois["meses_ate_alvo"], depois["aporte_mensal"]) == (2, "4500.00")


def _relogio_em(monkeypatch: pytest.MonkeyPatch, instante_utc: datetime) -> None:
    class RelogioFalso(datetime):
        @classmethod
        def now(cls, tz: Any = None) -> RelogioFalso:
            return cls.fromtimestamp(instante_utc.timestamp(), tz)

    monkeypatch.setattr(svc_data, "datetime", RelogioFalso)


@pytest.mark.parametrize(
    ("utc", "meses"),
    [
        (datetime(2026, 5, 1, 2, 30, tzinfo=UTC), 3),  # 30/04 23:30 em São Paulo
        (datetime(2026, 5, 1, 3, 30, tzinfo=UTC), 2),  # 01/05 00:30 em São Paulo
    ],
)
def test_hoje_usa_o_fuso_de_sao_paulo(
    client: TestClient,
    usuario: Usuario,
    monkeypatch: pytest.MonkeyPatch,
    utc: datetime,
    meses: int,
) -> None:
    """SPEC-009-AC-10: o caminho de produção (sem override) decide pelo fuso, não por UTC."""
    c = Cenario(client, usuario)
    c.reserva("Reserva", "3000.00")
    c.parametros("4000.00", alvo="2026-07-15")
    _relogio_em(monkeypatch, utc)
    r = client.get("/api/reserva")
    assert r.status_code == 200 and r.json()["meses_ate_alvo"] == meses


def test_hoje_nao_vem_do_cliente(client: TestClient, usuario: Usuario) -> None:
    """SPEC-009-AC-10: `hoje` e `user_id` na query são ignorados."""
    c = Cenario(client, usuario)
    c.reserva("Reserva", "3000.00")
    c.parametros("4000.00")
    r = client.get("/api/reserva", params={"hoje": "1999-01-01", "user_id": 1})
    assert r.status_code == 200 and r.json()["config_pendente"] is False


# ------------------------------------------------------------------ validação e erros


@pytest.mark.parametrize(
    "campos",
    [
        {"meses": 0},
        {"meses": 121},
        {"gasto_essencial": "1000000000.00"},
        {"vigente_desde": "1999-12-31"},
        {"data_alvo": "1999-12-31"},
    ],
)
def test_limites_de_negocio_sao_ab422_do_banco(
    client: TestClient, usuario: Usuario, campos: dict[str, Any]
) -> None:
    """SPEC-009-AC-10: N fora de 1..120, gasto de 1 bilhão e datas antes de 2000 voltam 422 com
    X-Abako-Erro: AB422 e mensagem literal; a conexão segue utilizável."""
    csrf = logar(client, usuario)
    corpo = {
        "meses": 3,
        "gasto_essencial": "100.00",
        "data_alvo": None,
        "vigente_desde": "2026-01-01",
        **campos,
    }
    r = client.put("/api/reserva/parametros", json=corpo, headers=escrita(csrf))
    assert r.status_code == 422, r.text
    assert r.headers["X-Abako-Erro"] == "AB422"
    assert isinstance(r.json()["detail"], str)
    for valor in ("1000000000", "1999-12-31"):
        assert valor not in r.json()["detail"]
    assert client.get("/api/reserva/parametros").json() == []


@pytest.mark.parametrize(
    "corpo",
    [
        {"meses": 3, "gasto_essencial": "-1.00", "vigente_desde": "2026-01-01"},
        {"meses": 3, "gasto_essencial": "10.123", "vigente_desde": "2026-01-01"},
        {"meses": 3, "gasto_essencial": "abc", "vigente_desde": "2026-01-01"},
        {"meses": "tres", "gasto_essencial": "10.00", "vigente_desde": "2026-01-01"},
        {"meses": 3, "gasto_essencial": 10.5, "vigente_desde": "2026-01-01"},
        {"meses": 3, "gasto_essencial": "10.00"},
        {"meses": 3, "gasto_essencial": "10.00", "vigente_desde": "ontem"},
        {"meses": 3, "gasto_essencial": "10.00", "vigente_desde": "2026-01-01", "x": 1},
    ],
)
def test_corpo_invalido_e_422_sem_eco(
    client: TestClient, usuario: Usuario, corpo: dict[str, Any]
) -> None:
    """SPEC-009-AC-10: corpo mal formado (inclusive float e chave desconhecida) é 422 e o valor
    recebido não volta na resposta."""
    csrf = logar(client, usuario)
    r = client.put("/api/reserva/parametros", json=corpo, headers=escrita(csrf))
    assert r.status_code == 422, r.text
    assert all("input" not in erro for erro in r.json()["detail"])
    for valor in ("10.123", "abc", "-1.00", "ontem"):
        if valor in corpo.values():
            assert valor not in r.text


def test_user_id_no_corpo_e_descartado(
    client: TestClient, usuario: Usuario, outro_usuario: Usuario
) -> None:
    """SPEC-009-AC-10 (INV-13): `user_id` no corpo não grava para o outro usuário."""
    csrf = logar(client, usuario)
    r = client.put(
        "/api/reserva/parametros",
        json={
            "meses": 3,
            "gasto_essencial": "100.00",
            "vigente_desde": "2026-01-01",
            "user_id": outro_usuario.user_id,
        },
        headers=escrita(csrf),
    )
    assert r.status_code == 200, r.text
    client.post("/api/auth/logout", headers=escrita(csrf))
    client.cookies.clear()
    logar(client, outro_usuario)
    assert client.get("/api/reserva/parametros").json() == []


# ------------------------------------------------------------------ sessão, CSRF, isolamento


def test_sem_sessao_e_401(client: TestClient) -> None:
    """SPEC-009-AC-10: as três rotas exigem sessão."""
    assert client.get("/api/reserva").status_code == 401
    assert client.get("/api/reserva/parametros").status_code == 401
    corpo = {"meses": 3, "gasto_essencial": "100.00", "vigente_desde": "2026-01-01"}
    assert client.put("/api/reserva/parametros", json=corpo, headers=ORIGEM).status_code == 401


def test_escrita_sem_csrf_e_403(client: TestClient, usuario: Usuario) -> None:
    """SPEC-009-AC-10: sem token CSRF (ou com token errado) a escrita é 403 e nada é gravado."""
    logar(client, usuario)
    corpo = {"meses": 3, "gasto_essencial": "100.00", "vigente_desde": "2026-01-01"}
    assert client.put("/api/reserva/parametros", json=corpo, headers=ORIGEM).status_code == 403
    errado = {**ORIGEM, "X-CSRF-Token": "errado"}
    assert client.put("/api/reserva/parametros", json=corpo, headers=errado).status_code == 403
    assert client.get("/api/reserva/parametros").json() == []


def test_isolamento_entre_usuarios(
    client: TestClient, usuario: Usuario, outro_usuario: Usuario
) -> None:
    """SPEC-009-AC-10 (INV-13): o outro usuário não vê reserva nem parâmetros do dono."""
    c = Cenario(client, usuario)
    reserva = c.reserva("Reserva", "5000.00")
    c.rendimento(reserva, "2026-02-10", "100.00", "22.50")
    c.parametros("1500.00", alvo="2026-12-01")
    assert em(client, "2026-04-01")["saldo_liquido"] == "5077.50"
    client.post("/api/auth/logout", headers=escrita(c.csrf))
    client.cookies.clear()

    logar(client, outro_usuario)
    s = em(client, "2026-04-01")
    assert (s["contas_reserva"], s["saldo_liquido"], s["imposto_acumulado"]) == (0, "0.00", "0.00")
    assert s["config_pendente"] is True and s["data_alvo"] is None
    assert client.get("/api/reserva/parametros", params={"user_id": usuario.user_id}).json() == []


def test_valores_fora_do_log(
    client: TestClient, usuario: Usuario, caplog: pytest.LogCaptureFixture
) -> None:
    """SPEC-009-AC-10: nenhum valor financeiro vai a log, nas leituras nem na gravação."""
    c = Cenario(client, usuario)
    reserva = c.reserva("Reserva", "5000.00")
    c.rendimento(reserva, "2026-02-10", "100.00", "22.50")
    with caplog.at_level(logging.DEBUG):
        c.parametros("1500.00", alvo="2026-12-01")
        em(client, "2026-04-01")
        client.get("/api/reserva/parametros")
    for valor in ("5077.50", "5100.00", "22.50", "1500.00", "4500.00"):
        assert valor not in caplog.text


def test_metodos_nao_previstos(client: TestClient, usuario: Usuario) -> None:
    """A situação é só GET; os parâmetros só GET e PUT."""
    csrf = logar(client, usuario)
    for metodo in ("post", "put", "delete"):
        r = getattr(client, metodo)("/api/reserva", headers=escrita(csrf))
        assert r.status_code == 405, metodo
    for metodo in ("post", "delete"):
        r = getattr(client, metodo)("/api/reserva/parametros", headers=escrita(csrf))
        assert r.status_code == 405, metodo
