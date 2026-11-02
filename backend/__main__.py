"""Sobe a API só em 127.0.0.1 (ADR 031/035): `python -m backend`."""

from __future__ import annotations

import uvicorn

import backend.db  # noqa: F401  # fixa a política de event loop do Windows antes do uvicorn
from backend.app import criar_app
from backend.settings import obter_settings

if __name__ == "__main__":
    cfg = obter_settings()
    uvicorn.run(criar_app(cfg), host="127.0.0.1", port=cfg.porta, loop="none")
