"""Consumidor de exemplo — usa o facade; nunca importa SDK vault."""

from __future__ import annotations

import logging

LOGGER = logging.getLogger(__name__)


def load_connection_ref(secret_ref: str, *, get_secret: object) -> str:
    """Obtém referência via facade injetado; não loga o valor."""
    # get_secret tipado como object para o stub não acoplar SDK
    value = get_secret(secret_ref)  # type: ignore[operator]
    LOGGER.info("secret.resolved", extra={"ref_present": bool(secret_ref)})
    return value
