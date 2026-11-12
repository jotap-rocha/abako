"""SPEC-010 / ADR 048: recorrente versionado, ocorrência derivada e vínculo com a transação.

Esperados de F-R2-10 e F-R2-11 (fixtures/numericos.yaml), calculados à mão.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import psycopg
import pytest

from tests.db.util_lancamento import Recusa, conta, excluir, lancar
from tests.db.util_r2 import (
    desvincular,
    excluir_recorrente,
    novo_cartao,
    ocorrencias,
    recorrente,
    situacao,
    usuario_com_corrente,
    vincular,
)
from tests.db.util_saldo import dec, dia, fixture

pytestmark = pytest.mark.banco


def test_dia_29_a_31_f_r2_10(conn: psycopg.Connection) -> None:
    """AC-5: o dia que não existe no mês usa o último dia válido (ADR 027)."""
    f = fixture("F-R2-10")
    e, esperado = f["entrada"], f["esperado"]
    uid, corrente = usuario_com_corrente(conn)
    for r in e["recorrentes"]:
        recorrente(
            conn, uid, f"dia_{r['dia']}", "fixo", "10.00", r["dia"], corrente, e["mes_inicio"]
        )
    for r in e["recorrentes"]:
        obtidas = []
        for mes in e["meses"]:
            [o] = [x for x in ocorrencias(conn, uid, mes) if x["nome"] == f"dia_{r['dia']}"]
            obtidas.append(o["data"])
        assert obtidas == [dia(t) for t in esperado[f"dia_{r['dia']}"]], r


def test_valor_e_vinculo_f_r2_11(conn: psycopg.Connection) -> None:
    """AC-4: valor esperado até vincular; depois o da transação; sai do R2 e volta ao desvincular"""
    f = fixture("F-R2-11")
    e, esperado = f["entrada"], f["esperado"]
    uid, corrente = usuario_com_corrente(conn, e["saldos_correntes"])
    r = e["recorrente"]
    rid, _ = recorrente(
        conn, uid, "assinatura", r["tipo"], r["valor"], r["dia"], corrente, r["mes_inicio"]
    )

    def maio() -> dict[str, object]:
        [o] = ocorrencias(conn, uid, "2026-05")
        return o

    antes = maio()
    alvo = esperado["antes"]["ocorrencia_2026_05"]
    assert (antes["data"], antes["valor"], antes["vinculada"]) == (
        dia(alvo["data"]),
        dec(alvo["valor"]),
        alvo["vinculada"],
    )
    assert antes["valor_esperado"] == dec("500.00") and antes["transacao_id"] is None
    assert situacao(conn, uid, e["hoje"])["compromissos"] == dec(esperado["antes"]["compromissos"])

    t = e["transacao"]
    pago, _, _ = lancar(conn, uid, t["tipo"], t["data"], corrente, t["valor"])
    vincular(conn, uid, rid, "2026-05", pago)
    ligada = maio()
    assert (ligada["valor"], ligada["vinculada"], ligada["transacao_id"]) == (
        dec(esperado["vinculada"]["ocorrencia_2026_05"]["valor"]),
        True,
        pago,
    )
    assert ligada["valor_esperado"] == dec("500.00")  # o esperado não muda
    assert situacao(conn, uid, e["hoje"])["compromissos"] == dec(
        esperado["vinculada"]["compromissos"]
    )

    desvincular(conn, uid, rid, "2026-05")
    solta = maio()
    assert (solta["valor"], solta["vinculada"]) == (dec("500.00"), False)
    assert situacao(conn, uid, e["hoje"])["compromissos"] == dec(
        esperado["desvinculada"]["compromissos"]
    )


def test_ocorrencias_so_no_periodo_do_recorrente(conn: psycopg.Connection) -> None:
    """Uma ocorrência por mês, de mes_inicio a mes_fim (inclusive); fora disso, nenhuma."""
    uid, corrente = usuario_com_corrente(conn)
    recorrente(conn, uid, "curso", "fixo", "50.00", 10, corrente, "2026-03", "2026-05")
    contagem = {
        m: len(ocorrencias(conn, uid, m)) for m in ("2026-02", "2026-03", "2026-05", "2026-06")
    }
    assert contagem == {"2026-02": 0, "2026-03": 1, "2026-05": 1, "2026-06": 0}
    with Recusa(conn, "AB422"):
        ocorrencias(conn, uid, "2026-13")


def test_transacao_excluida_devolve_a_ocorrencia(conn: psycopg.Connection) -> None:
    """AC-4: transação excluída ou movida de conta deixa de valer como vínculo (volta ao R2)."""
    uid, corrente = usuario_com_corrente(conn, "1000.00")
    outra = conta(conn, uid, "corrente_2")
    rid, _ = recorrente(conn, uid, "gas", "fixo", "80.00", 12, corrente, "2026-05")
    t, versao, _ = lancar(conn, uid, "debito", "2026-05-08", corrente, "80.00")
    vincular(conn, uid, rid, "2026-05", t)
    assert situacao(conn, uid, "2026-05-10")["fixos_pendentes"] == dec("0.00")

    # editada para outra conta: já não é a do recorrente
    lancar(conn, uid, "debito", "2026-05-08", outra, "80.00", transacao_id=t, versao=versao)
    [o] = ocorrencias(conn, uid, "2026-05")
    assert o["vinculada"] is False and o["valor"] == dec("80.00")
    assert situacao(conn, uid, "2026-05-10")["fixos_pendentes"] == dec("80.00")

    # de volta à conta do recorrente, o vínculo (que nunca foi apagado) vale de novo
    lancar(conn, uid, "debito", "2026-05-08", corrente, "75.00", transacao_id=t, versao=versao + 1)
    [o] = ocorrencias(conn, uid, "2026-05")
    assert (o["vinculada"], o["valor"]) == (True, dec("75.00"))

    # excluída: volta a pendente, mas o histórico do vínculo segue lá
    excluir(conn, uid, t, versao + 2)
    [o] = ocorrencias(conn, uid, "2026-05")
    assert o["vinculada"] is False
    assert situacao(conn, uid, "2026-05-10")["fixos_pendentes"] == dec("80.00")
    eventos = conn.execute(
        "SELECT count(*) FROM recorrente_vinculo WHERE user_id = %s", (uid,)
    ).fetchone()
    assert eventos == (1,)
    # com a transação excluída é possível ligar outra à mesma ocorrência
    nova, _, _ = lancar(conn, uid, "debito", "2026-05-09", corrente, "81.00")
    vincular(conn, uid, rid, "2026-05", nova)
    [o] = ocorrencias(conn, uid, "2026-05")
    assert (o["transacao_id"], o["valor"]) == (nova, dec("81.00"))


def test_vinculo_e_historico_append_only(conn: psycopg.Connection) -> None:
    """AC-4: vincular, desvincular e vincular de novo são eventos; nada é atualizado."""
    uid, corrente = usuario_com_corrente(conn, "1000.00")
    rid, _ = recorrente(conn, uid, "seguro", "fixo", "60.00", 8, corrente, "2026-05")
    a, _, _ = lancar(conn, uid, "debito", "2026-05-08", corrente, "60.00")
    b, _, _ = lancar(conn, uid, "debito", "2026-05-09", corrente, "61.00")
    e1 = vincular(conn, uid, rid, "2026-05", a)
    assert vincular(conn, uid, rid, "2026-05", a) == e1  # repetir é idempotente
    e2 = desvincular(conn, uid, rid, "2026-05")
    e3 = vincular(conn, uid, rid, "2026-05", b)
    assert e1 < e2 < e3
    linhas = conn.execute(
        "SELECT id, transacao_id FROM recorrente_vinculo WHERE user_id = %s ORDER BY id", (uid,)
    ).fetchall()
    assert linhas == [(e1, a), (e2, None), (e3, b)]
    vigente = conn.execute(
        "SELECT id, transacao_id FROM recorrente_vinculo_vigente WHERE user_id = %s", (uid,)
    ).fetchall()
    assert vigente == [(e3, b)]
    [o] = ocorrencias(conn, uid, "2026-05")
    assert (o["transacao_id"], o["valor"]) == (b, dec("61.00"))
    # a transação antiga ficou livre: pode ser de outro mês
    rid2, _ = recorrente(conn, uid, "seguro2", "fixo", "60.00", 8, corrente, "2026-05")
    vincular(conn, uid, rid2, "2026-05", a)


def test_recorrente_so_em_conta_corrente(conn: psycopg.Connection) -> None:
    """AC-8: fixo e receita recorrentes só em conta corrente (assinatura no cartão é compra)."""
    uid, corrente = usuario_com_corrente(conn)
    for n, tipo in enumerate(("reserva", "investimento", "beneficio")):
        mae = None if tipo == "beneficio" else corrente
        outra = conta(conn, uid, f"conta_{tipo}", tipo, mae=mae)
        for tipo_rec in ("fixo", "receita"):
            with Recusa(conn, "AB422"):
                recorrente(conn, uid, f"r{n}{tipo_rec}", tipo_rec, "10.00", 5, outra, "2026-05")
    cartao_id = novo_cartao(conn, uid, 10, 20)
    with Recusa(conn, "AB422"):
        recorrente(conn, uid, "assinatura", "fixo", "10.00", 5, cartao_id, "2026-05")
    with Recusa(conn, "AB404"):
        recorrente(conn, uid, "fantasma", "fixo", "10.00", 5, 987654321, "2026-05")
    recorrente(conn, uid, "ok", "fixo", "10.00", 5, corrente, "2026-05")
    assert situacao(conn, uid, "2026-05-01")["fixos_pendentes"] == dec("10.00")


def test_versionamento_do_recorrente(conn: psycopg.Connection) -> None:
    """AC-10: editar cria versão (exige a lida); excluir é lógico; o nome volta a ficar livre."""
    uid, corrente = usuario_com_corrente(conn, "1000.00")
    rid, v1 = recorrente(conn, uid, "Aluguel", "fixo", "500.00", 5, corrente, "2026-05")
    assert v1 == 1
    t, _, _ = lancar(conn, uid, "debito", "2026-05-05", corrente, "490.00")
    vincular(conn, uid, rid, "2026-05", t)

    _, v2 = recorrente(
        conn, uid, "Aluguel", "fixo", "600.00", 6, corrente, "2026-05", recorrente_id=rid, versao=v1
    )
    assert v2 == 2
    versoes = conn.execute(
        "SELECT versao, vigente, valor FROM recorrente WHERE user_id = %s ORDER BY versao", (uid,)
    ).fetchall()
    assert versoes == [(1, False, dec("500.00")), (2, True, dec("600.00"))]
    # a edição vale para as não vinculadas; a vinculada guarda o valor da transação
    [maio] = ocorrencias(conn, uid, "2026-05")
    assert (maio["valor"], maio["valor_esperado"], maio["data"]) == (
        dec("490.00"),
        dec("600.00"),
        date(2026, 5, 6),
    )
    [junho] = ocorrencias(conn, uid, "2026-06")
    assert (junho["valor"], junho["vinculada"]) == (dec("600.00"), False)

    with Recusa(conn, "AB409"):  # versão desatualizada
        recorrente(
            conn,
            uid,
            "Aluguel",
            "fixo",
            "700.00",
            6,
            corrente,
            "2026-05",
            recorrente_id=rid,
            versao=v1,
        )
    with Recusa(conn, "AB422"):  # editar exige a versão lida
        recorrente(
            conn, uid, "Aluguel", "fixo", "700.00", 6, corrente, "2026-05", recorrente_id=rid
        )
    with Recusa(conn, "AB404"):
        recorrente(
            conn,
            uid,
            "x",
            "fixo",
            "1.00",
            6,
            corrente,
            "2026-05",
            recorrente_id=987654321,
            versao=1,
        )
    with Recusa(conn, "AB410"):  # nome repetido, sem diferenciar maiúsculas
        recorrente(conn, uid, "ALUGUEL", "receita", "1.00", 6, corrente, "2026-05")

    with Recusa(conn, "AB409"):
        excluir_recorrente(conn, uid, rid, v1)
    assert excluir_recorrente(conn, uid, rid, v2) == 3
    assert ocorrencias(conn, uid, "2026-05") == []
    with Recusa(conn, "AB404"):
        excluir_recorrente(conn, uid, rid, 3)
    with Recusa(conn, "AB404"):
        recorrente(
            conn,
            uid,
            "Aluguel",
            "fixo",
            "1.00",
            6,
            corrente,
            "2026-05",
            recorrente_id=rid,
            versao=3,
        )
    with Recusa(conn, "AB404"):  # recorrente excluído não recebe vínculo
        vincular(conn, uid, rid, "2026-06", t)
    assert situacao(conn, uid, "2026-05-01")["fixos_pendentes"] == dec("0.00")
    recorrente(conn, uid, "Aluguel", "fixo", "1.00", 6, corrente, "2026-05")  # nome livre de novo
    historico = conn.execute(
        "SELECT count(*) FROM recorrente WHERE user_id = %s", (uid,)
    ).fetchone()
    assert historico == (4,)  # 3 versões do primeiro + 1 do novo; nada foi apagado


def test_validacoes_do_recorrente(conn: psycopg.Connection) -> None:
    """AC-10: cada campo inválido é recusado com AB422 (mensagem literal)."""
    uid, corrente = usuario_com_corrente(conn)
    base: dict[str, Any] = {
        "nome": "ok",
        "tipo": "fixo",
        "valor": "10.00",
        "dia_mes": 5,
        "inicio": "2026-05",
    }
    invalidos: list[dict[str, Any]] = [
        {"nome": "   "},
        {"nome": "x" * 81},
        {"tipo": "despesa"},
        {"tipo": None},
        {"valor": "0.00"},
        {"valor": "-1.00"},
        {"valor": "1.234"},
        {"valor": "1000000000000.00"},
        {"dia_mes": 0},
        {"dia_mes": 32},
        {"inicio": None},
        {"inicio": "2026-5"},
        {"inicio": "1999-12"},
        {"fim": "2026-04"},
        {"fim": "2026-13"},
    ]
    for troca in invalidos:
        campos = {**base, **troca}
        with Recusa(conn, "AB422"):
            recorrente(
                conn,
                uid,
                campos["nome"],
                campos["tipo"],
                campos["valor"],
                campos["dia_mes"],
                corrente,
                campos["inicio"],
                campos.get("fim"),
            )
    with Recusa(conn, "AB422"):  # valor ausente
        conn.execute(
            "SELECT * FROM recorrente_gravar("
            "%s, NULL, NULL, 'a', 'fixo', NULL, 5, %s, '2026-05', NULL)",
            (uid, corrente),
        )
    with Recusa(conn, "AB404"):
        recorrente(conn, 999999999, "ok", "fixo", "10.00", 5, corrente, "2026-05")
    outro, conta_outro = usuario_com_corrente(conn)
    with Recusa(conn, "AB404"):  # conta de outro usuário
        recorrente(conn, uid, "ok", "fixo", "10.00", 5, conta_outro, "2026-05")
    assert outro != uid
    # nada ficou gravado pelas tentativas recusadas
    assert conn.execute(
        "SELECT count(*) FROM recorrente WHERE user_id = %s", (uid,)
    ).fetchone() == (0,)


def test_regras_do_vinculo(conn: psycopg.Connection) -> None:
    """AC-10: tipo e conta da transação, uma transação por ocorrência e período do recorrente."""
    uid, corrente = usuario_com_corrente(conn, "1000.00")
    outra = conta(conn, uid, "corrente_2")
    fixo, vf = recorrente(conn, uid, "fixo", "fixo", "100.00", 10, corrente, "2026-05", "2026-07")
    rec, _ = recorrente(conn, uid, "salario", "receita", "900.00", 10, corrente, "2026-05")
    debito, _, _ = lancar(conn, uid, "debito", "2026-05-10", corrente, "100.00")
    entrada, _, _ = lancar(conn, uid, "receita", "2026-05-10", corrente, "900.00")
    debito_outra, _, _ = lancar(conn, uid, "debito", "2026-05-10", outra, "100.00")

    with Recusa(conn, "AB404"):
        vincular(conn, uid, fixo, "2026-05", 987654321)  # transação inexistente
    with Recusa(conn, "AB404"):
        vincular(conn, uid, 987654321, "2026-05", debito)  # recorrente inexistente
    with Recusa(conn, "AB422"):
        vincular(conn, uid, fixo, "2026-05", entrada)  # fixo exige débito
    with Recusa(conn, "AB422"):
        vincular(conn, uid, rec, "2026-05", debito)  # receita exige receita
    with Recusa(conn, "AB422"):
        vincular(conn, uid, fixo, "2026-05", debito_outra)  # conta diferente
    with Recusa(conn, "AB422"):
        vincular(conn, uid, fixo, "2026-04", debito)  # antes do período
    with Recusa(conn, "AB422"):
        vincular(conn, uid, fixo, "2026-08", debito)  # depois do período
    with Recusa(conn, "AB422"):
        vincular(conn, uid, fixo, "maio", debito)  # mês inválido
    with Recusa(conn, "AB404"):
        desvincular(conn, uid, fixo, "2026-05")  # nada a desvincular

    vincular(conn, uid, fixo, "2026-05", debito)
    outro_debito, _, _ = lancar(conn, uid, "debito", "2026-05-11", corrente, "100.00")
    with Recusa(conn, "AB410"):  # a ocorrência já tem outra transação
        vincular(conn, uid, fixo, "2026-05", outro_debito)
    with Recusa(conn, "AB410"):  # a transação já está em outra ocorrência (outro mês)
        vincular(conn, uid, fixo, "2026-06", debito)

    with Recusa(conn, "AB422"):  # tipo não muda depois de haver vínculo
        recorrente(
            conn,
            uid,
            "fixo",
            "receita",
            "100.00",
            10,
            corrente,
            "2026-05",
            "2026-07",
            recorrente_id=fixo,
            versao=vf,
        )
    with Recusa(conn, "AB422"):  # conta não muda depois de haver vínculo
        recorrente(
            conn,
            uid,
            "fixo",
            "fixo",
            "100.00",
            10,
            outra,
            "2026-05",
            "2026-07",
            recorrente_id=fixo,
            versao=vf,
        )
    with Recusa(conn, "AB422"):  # o período não pode deixar o vínculo de fora
        recorrente(
            conn,
            uid,
            "fixo",
            "fixo",
            "100.00",
            10,
            corrente,
            "2026-06",
            "2026-07",
            recorrente_id=fixo,
            versao=vf,
        )
    with Recusa(conn, "AB422"):
        recorrente(
            conn,
            uid,
            "fixo",
            "fixo",
            "100.00",
            10,
            corrente,
            "2026-01",
            "2026-04",
            recorrente_id=fixo,
            versao=vf,
        )
    # nome, valor, dia e período que mantêm o vínculo podem mudar
    _, v2 = recorrente(
        conn,
        uid,
        "fixo",
        "fixo",
        "120.00",
        11,
        corrente,
        "2026-04",
        None,
        recorrente_id=fixo,
        versao=vf,
    )
    assert v2 == vf + 1
    desvincular(conn, uid, fixo, "2026-05")
    with Recusa(conn, "AB422"):  # desvinculado, mas o histórico de vínculos ainda impede
        recorrente(
            conn,
            uid,
            "fixo",
            "receita",
            "120.00",
            11,
            corrente,
            "2026-04",
            recorrente_id=fixo,
            versao=v2,
        )


def test_isolamento_do_recorrente(conn: psycopg.Connection) -> None:
    """AC-11 / INV-13: recorrente e transação de outro usuário não podem ser usados."""
    dono, c_dono = usuario_com_corrente(conn, "1000.00")
    rid, versao = recorrente(conn, dono, "meu", "fixo", "10.00", 5, c_dono, "2026-05")
    t, _, _ = lancar(conn, dono, "debito", "2026-05-05", c_dono, "10.00")
    outro, c_outro = usuario_com_corrente(conn, "1000.00")
    t_outro, _, _ = lancar(conn, outro, "debito", "2026-05-05", c_outro, "10.00")
    rid_outro, _ = recorrente(conn, outro, "dele", "fixo", "10.00", 5, c_outro, "2026-05")

    with Recusa(conn, "AB404"):
        vincular(conn, outro, rid, "2026-05", t)  # recorrente do dono
    with Recusa(conn, "AB404"):
        vincular(conn, outro, rid_outro, "2026-05", t)  # transação do dono
    with Recusa(conn, "AB404"):
        vincular(conn, dono, rid_outro, "2026-05", t)
    with Recusa(conn, "AB404"):
        desvincular(conn, outro, rid, "2026-05")
    with Recusa(conn, "AB404"):
        excluir_recorrente(conn, outro, rid, versao)
    with Recusa(conn, "AB404"):
        recorrente(
            conn,
            outro,
            "meu",
            "fixo",
            "1.00",
            5,
            c_outro,
            "2026-05",
            recorrente_id=rid,
            versao=versao,
        )
    vincular(conn, outro, rid_outro, "2026-05", t_outro)  # o próprio funciona
    assert [o["nome"] for o in ocorrencias(conn, outro, "2026-05")] == ["dele"]
    assert [o["nome"] for o in ocorrencias(conn, dono, "2026-05")] == ["meu"]
    assert [o["vinculada"] for o in ocorrencias(conn, dono, "2026-05")] == [False]
