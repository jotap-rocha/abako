"""Dinheiro na borda da API: Decimal no Python, texto no JSON (INV-14). Nunca float."""

from __future__ import annotations

from decimal import Decimal


def texto_dinheiro(valor: Decimal) -> str:
    """'1050.00': duas casas, sem notação científica. O banco já guarda numeric(14,2)."""
    return f"{valor:.2f}"
