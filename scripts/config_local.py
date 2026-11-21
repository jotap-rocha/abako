"""Lê, num processo filho, a configuração local que o arquivo de variáveis define (ADR 056).

Por que existe: `scripts/operacao.py` nunca abre o arquivo de variáveis; quem o carrega são os
módulos do projeto. Este módulo roda como processo à parte, carrega as variáveis do jeito de
sempre (`db.alvo.carregar_env`) e devolve só o que o operador precisa para achar o contêiner, a
pasta de backups e a porta da API: nomes e um número, nenhuma senha nem URL de conexão.

Uso: `python -m scripts.config_local` (imprime uma linha JSON).
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping

from db.alvo import AlvoInvalido, carregar_env
from db.conteiner import nome_conteiner
from scripts.backup import pasta_backup

VAR_PORTA = "ABAKO_PORTA"
PORTA_PADRAO = 8080


def porta_valida(valor: str | None) -> int:
    """Porta da API: vazio ou ausente = 8080; senão inteiro de 1 a 65535 (`ValueError` se não)."""
    texto = (valor or "").strip()
    if not texto:
        return PORTA_PADRAO
    if not (texto.isascii() and texto.isdigit()) or not 1 <= int(texto) <= 65535:
        raise ValueError(f"{VAR_PORTA} inválida: use um número de 1 a 65535")
    return int(texto)


def coletar(environ: Mapping[str, str]) -> dict[str, str | int]:
    """`conteiner`, `pasta` (de backup) e `porta`; o que não puder ser resolvido fica de fora.

    Porta inválida vira `porta_invalida` (o operador recusa com mensagem clara, sem repetir o
    valor).
    """
    saida: dict[str, str | int] = {}
    try:
        saida["conteiner"] = nome_conteiner(environ)
    except AlvoInvalido:
        pass
    try:
        saida["pasta"] = str(pasta_backup(environ))
    except AlvoInvalido:
        pass
    try:
        saida["porta"] = porta_valida(environ.get(VAR_PORTA))
    except ValueError:
        saida["porta_invalida"] = "sim"
    return saida


def main() -> int:
    carregar_env()
    print(json.dumps(coletar(dict(os.environ))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
