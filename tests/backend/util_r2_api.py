"""Montagem de cenários do R2 e dos recorrentes pela API (SPEC-010, ADR 048), sempre via HTTP."""

from __future__ import annotations

import itertools
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from typing import Any

from fastapi.testclient import TestClient

from backend.routers import r2 as router_r2
from backend.routers import recorrentes as router_recorrentes
from tests.backend.conftest import ORIGEM, Usuario, logar

_contador = itertools.count(1)


def escrita(csrf: str) -> dict[str, str]:
    return {**ORIGEM, "X-CSRF-Token": csrf}


def chave() -> str:
    return f"chave-{next(_contador):08d}"


@contextmanager
def hoje_em(client: TestClient, hoje: str) -> Iterator[None]:
    """Injeta `hoje` (a rota nunca recebe a data do cliente)."""
    app: Any = client.app
    fixa = date.fromisoformat(hoje)
    app.dependency_overrides[router_r2.hoje_civil] = lambda: fixa
    app.dependency_overrides[router_recorrentes.hoje_civil] = lambda: fixa
    try:
        yield
    finally:
        app.dependency_overrides.clear()


class Cenario:
    """Contas, cartões, transações, recorrentes e parâmetros de um usuário, só pela API."""

    def __init__(self, client: TestClient, usuario: Usuario, saldo: str | None = "0.00") -> None:
        self.client = client
        self.csrf = logar(client, usuario)
        self.corrente = self.conta("Corrente", "corrente")
        if saldo is not None:
            self.snapshot(self.corrente, saldo)

    # ---- contas e lançamentos
    def conta(self, nome: str, tipo: str, **campos: Any) -> int:
        corpo = {"nome": nome, "tipo": tipo, "conta_beneficio": tipo == "beneficio", **campos}
        r = self.client.post("/api/contas", json=corpo, headers=escrita(self.csrf))
        assert r.status_code == 201, r.text
        conta_id: int = r.json()["conta_id"]
        return conta_id

    def snapshot(self, conta_id: int, valor: str, data: str = "2026-01-01") -> None:
        r = self.client.post(
            f"/api/contas/{conta_id}/snapshots",
            json={"data": data, "valor": valor},
            headers=escrita(self.csrf),
        )
        assert r.status_code == 201, r.text

    def cartao(
        self,
        fechamento: int,
        vencimento: int | None,
        nome: str = "Cartao",
        desde: str = "2026-01-01",
    ) -> int:
        r = self.client.post(
            "/api/linhas-credito",
            json={"nome": f"Linha {nome}", "limite": "100000"},
            headers=escrita(self.csrf),
        )
        assert r.status_code == 201, r.text
        cartao = self.conta(nome, "divida", linha_credito_id=r.json()["linha_id"])
        r = self.client.post(
            f"/api/cartoes/{cartao}/fechamentos",
            json={"dia": fechamento, "vigente_desde": desde},
            headers=escrita(self.csrf),
        )
        assert r.status_code == 201, r.text
        if vencimento is not None:
            self.vencimento(cartao, vencimento, desde)
        return cartao

    def vencimento(self, cartao: int, dia: int, desde: str = "2026-01-01") -> Any:
        return self.client.put(
            f"/api/cartoes/{cartao}/vencimentos",
            json={"dia": dia, "vigente_desde": desde},
            headers=escrita(self.csrf),
        )

    def lancar(self, **campos: Any) -> dict[str, Any]:
        corpo = {"chave": chave(), **campos}
        r = self.client.post("/api/lancamentos", json=corpo, headers=escrita(self.csrf))
        assert r.status_code == 201, r.text
        saida: dict[str, Any] = r.json()
        return saida

    def compra(
        self, cartao: int, data: str, valor: str, pessoa_id: int | None = None
    ) -> dict[str, Any]:
        return self.lancar(
            tipo="credito",
            data=data,
            valor=valor,
            parcelas=1,
            conta_id=cartao,
            pessoa_id=pessoa_id,
        )

    def pagar(self, cartao: int, data: str, valor: str) -> dict[str, Any]:
        return self.lancar(
            tipo="transferencia",
            data=data,
            valor=valor,
            conta_id=self.corrente,
            conta_destino_id=cartao,
        )

    def debito(self, data: str, valor: str, conta: int | None = None) -> dict[str, Any]:
        return self.lancar(tipo="debito", data=data, valor=valor, conta_id=conta or self.corrente)

    def receita(self, data: str, valor: str, conta: int | None = None) -> dict[str, Any]:
        return self.lancar(tipo="receita", data=data, valor=valor, conta_id=conta or self.corrente)

    def pessoa(self, nome: str = "Pessoa B") -> int:
        r = self.client.post("/api/pessoas", json={"nome": nome}, headers=escrita(self.csrf))
        assert r.status_code == 201, r.text
        pessoa_id: int = r.json()["pessoa_id"]
        return pessoa_id

    # ---- recorrentes e R2
    def corpo(
        self,
        nome: str,
        tipo: str = "fixo",
        valor: str = "100.00",
        dia: int = 5,
        inicio: str = "2026-05",
        fim: str | None = None,
        conta: int | None = None,
    ) -> dict[str, Any]:
        return {
            "nome": nome,
            "tipo": tipo,
            "valor": valor,
            "dia": dia,
            "conta_id": conta or self.corrente,
            "mes_inicio": inicio,
            "mes_fim": fim,
        }

    def recorrente(self, nome: str, **campos: Any) -> dict[str, Any]:
        r = self.client.post(
            "/api/recorrentes", json=self.corpo(nome, **campos), headers=escrita(self.csrf)
        )
        assert r.status_code == 201, r.text
        saida: dict[str, Any] = r.json()
        return saida

    def vincular(self, recorrente_id: int, mes: str, transacao_id: int) -> Any:
        return self.client.put(
            f"/api/recorrentes/{recorrente_id}/ocorrencias/{mes}/vinculo",
            json={"transacao_id": transacao_id},
            headers=escrita(self.csrf),
        )

    def desvincular(self, recorrente_id: int, mes: str) -> Any:
        return self.client.delete(
            f"/api/recorrentes/{recorrente_id}/ocorrencias/{mes}/vinculo",
            headers=escrita(self.csrf),
        )

    def horizonte(self, dias: int, desde: str = "2026-01-01") -> Any:
        return self.client.put(
            "/api/r2/horizonte",
            json={"dias": dias, "vigente_desde": desde},
            headers=escrita(self.csrf),
        )


def r2_em(client: TestClient, hoje: str) -> dict[str, Any]:
    with hoje_em(client, hoje):
        r = client.get("/api/r2")
    assert r.status_code == 200, r.text
    corpo: dict[str, Any] = r.json()
    return corpo


def resumo(s: dict[str, Any], *campos: str) -> dict[str, Any]:
    return {c: s[c] for c in campos}
