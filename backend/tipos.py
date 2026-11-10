"""Listas fechadas do domínio usadas pela API (ADR 011/042). O banco tem os mesmos CHECKs."""

from __future__ import annotations

from typing import Literal

TipoConta = Literal["corrente", "reserva", "investimento", "beneficio"]
TipoLancamento = Literal[
    "debito", "credito", "receita", "transferencia", "investimento", "repasse", "rendimento"
]
