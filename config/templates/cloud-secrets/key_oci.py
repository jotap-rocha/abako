"""Facade OCI Vault — ponto único de resolução de secret (stub sem live API).

Consumidores importam apenas este módulo. Nunca logue o valor retornado.
"""

from __future__ import annotations


def get_secret(secret_id: str) -> str:
    """Resolve um secret pelo OCID / id lógico.

    Em runtime real: use o SDK OCI *somente aqui* (Resource Principal ou config local).
    Neste scaffold canônico não há chamada live — placeholders no map bastam para o gate.
    """
    if not secret_id or secret_id.startswith("<"):
        raise ValueError("secret_id deve ser um OCID/placeholder válido no secrets_map")
    raise NotImplementedError(
        "sem live API neste scaffold canônico — implemente com oci.secrets só neste facade"
    )
