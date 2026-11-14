"""Montagem do VR pela API (SPEC-013), compartilhada pelos testes do vale e dos alertas."""

from __future__ import annotations

from decimal import Decimal

from tests.backend.util_r2_api import Cenario, escrita


def marcar_vr(
    c: Cenario, base: str = "200.00", destino: str = "nenhum", desde: str = "2025-01-01"
) -> int:
    """Cria a conta de benefício e a marca como VR (parâmetro do vale)."""
    vr = c.conta("VR", "beneficio")
    r = c.client.put(
        "/api/vale/parametro",
        json={
            "conta_id": vr,
            "base_trabalho": base,
            "destino_padrao": destino,
            "vigente_desde": desde,
        },
        headers=escrita(c.csrf),
    )
    assert r.status_code == 200, r.text
    return vr


def mes_do_vr(
    c: Cenario, vr: int, mes: str, credito: str, trabalho: str = "0.00", pessoal: str = "0.00"
) -> None:
    """Receita no dia 5 e, se houver, uma despesa por bolso no dia 10."""
    if Decimal(credito) > 0:
        c.receita(f"{mes}-05", credito, conta=vr)
    for bolso, valor in (("trabalho", trabalho), ("pessoal", pessoal)):
        if Decimal(valor) > 0:
            c.lancar(tipo="debito", data=f"{mes}-10", valor=valor, conta_id=vr, bolso=bolso)
