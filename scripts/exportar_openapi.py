"""Exporta o contrato OpenAPI da API para `frontend/openapi.json` (fonte do cliente TS, ADR 015).

Uso: `.venv\\Scripts\\python.exe -m scripts.exportar_openapi`, depois `npm run gen:api` em
`frontend/`. A checagem `tests/contracts/test_cliente_openapi.py` falha se algum dos dois
estiver defasado.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import SecretStr

from backend.app import criar_app
from backend.settings import Settings

RAIZ = Path(__file__).resolve().parent.parent
DESTINO = RAIZ / "frontend" / "openapi.json"


def contrato_atual() -> dict[str, Any]:
    """O contrato não depende do banco: a URL é só um valor exigido pelas configurações."""
    app = criar_app(Settings(db_app_url=SecretStr("sem-conexao"), frontend_dist=RAIZ / "nada"))
    contrato: dict[str, Any] = app.openapi()
    return contrato


def serializar(contrato: dict[str, Any]) -> str:
    return json.dumps(contrato, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main() -> int:
    DESTINO.write_text(serializar(contrato_atual()), encoding="utf-8", newline="\n")
    print(f"contrato escrito em {DESTINO.relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
