"""Facade Azure Key Vault — ponto único de resolução de secret (stub sem live API).

Consumidores importam apenas este módulo. Nunca logue o valor retornado.
"""

from __future__ import annotations


def get_secret(secret_name_or_uri: str) -> str:
    """Resolve um secret pelo nome ou URI do Key Vault.

    Em runtime real: use azure.keyvault + DefaultAzureCredential *somente aqui*.
    Neste scaffold canônico não há chamada live — placeholders no map bastam para o gate.
    """
    if not secret_name_or_uri or secret_name_or_uri.startswith("<"):
        raise ValueError("informe URI/nome presente no secrets_map")
    raise NotImplementedError(
        "sem live API neste scaffold canônico — implemente com azure.keyvault só neste facade"
    )
