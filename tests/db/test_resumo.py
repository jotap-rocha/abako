"""Resumo de conferência da restauração (SPEC-001-AC-14), contra o `tst` real.

Linhas sintéticas inseridas na transação do teste (desfeitas no rollback). Esperado à mão:
1 usuário, 1 conta, 3 transações de "100.10", "-30.05" e "0.95": soma(valor) = 71.00
(100.10 - 30.05 = 70.05; 70.05 + 0.95 = 71.00).
"""

from __future__ import annotations

from decimal import Decimal

import psycopg
import pytest

from db.resumo import banco_vazio, conectar_somente_leitura, formatar, resumir
from scripts import resumo_banco

pytestmark = pytest.mark.banco

VALORES = ["100.10", "-30.05", "0.95"]


def _semear(conn: psycopg.Connection[tuple[object, ...]]) -> None:
    linha = conn.execute(
        "INSERT INTO usuario (login) VALUES ('sintetico-resumo') RETURNING user_id"
    ).fetchone()
    assert linha is not None
    uid = linha[0]
    linha = conn.execute(
        "INSERT INTO conta_versao (user_id, nome) VALUES (%s, 'conta sintetica') "
        "RETURNING conta_id",
        (uid,),
    ).fetchone()
    assert linha is not None
    for v in VALORES:
        conn.execute(
            "INSERT INTO transacao_versao (user_id, conta_id, data_transacao, valor, tipo) "
            "VALUES (%s, %s, DATE '2026-10-01', %s::numeric, "
            "CASE WHEN %s::numeric < 0 THEN 'debito' ELSE 'receita' END)",
            (uid, linha[0], v, v),
        )


def test_resumir_confere_contagem_e_soma(conn: psycopg.Connection[tuple[object, ...]]) -> None:
    antes = {r.tabela: r for r in resumir(conn)}
    for t in ("usuario", "conta_versao", "transacao_versao"):
        assert antes[t].linhas == 0, "o tst deve estar vazio (dados de teste vazaram?)"
    _semear(conn)
    depois = {r.tabela: r for r in resumir(conn)}
    assert depois["usuario"].linhas == 1 and depois["usuario"].somas == {}
    assert depois["conta_versao"].linhas == 1 and depois["conta_versao"].somas == {}
    assert depois["transacao_versao"].linhas == 3
    assert depois["transacao_versao"].somas == {
        "valor": Decimal("71.00"),
        "bruto": Decimal("0"),
        "imposto": Decimal("0"),
        "estorno_credito": Decimal("0"),  # coluna da 0007; a soma cobre toda coluna numérica
    }
    assert banco_vazio(conn) is False

    texto = "\n".join(formatar(list(depois.values())))
    assert "transacao_versao: 3 linhas; soma(valor)=71.00" in texto
    for v in VALORES:  # nenhum valor individual aparece
        assert v not in texto
    assert "sintetico" not in texto


def test_conexao_do_resumo_e_somente_leitura(esquema: str) -> None:
    with conectar_somente_leitura(esquema) as c:
        assert c.execute("SELECT current_database()").fetchone() == ("tst",)
        with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
            c.execute("INSERT INTO usuario (login) VALUES ('nao-deve-gravar')")


def test_resumo_banco_usa_conexao_somente_leitura(
    esquema: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    chamadas: list[str] = []

    def espiao(url: str) -> psycopg.Connection[tuple[object, ...]]:
        chamadas.append(url)
        conn = conectar_somente_leitura(url)
        assert conn.read_only is True
        return conn

    monkeypatch.setattr(resumo_banco, "conectar_somente_leitura", espiao)
    assert resumo_banco.main(["--alvo", "tst"]) == 0
    assert len(chamadas) == 1
    assert "transacao_versao:" in capsys.readouterr().out
