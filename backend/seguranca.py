"""Senha (Argon2id), tokens de sessão/CSRF e limite de tentativas de login."""

from __future__ import annotations

import hashlib
import secrets
import time
from collections import deque
from collections.abc import Callable

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

# Mínimo OWASP para Argon2id: 19 MiB, t=2, p=1 (ADR 020).
HASHER = PasswordHasher(memory_cost=19 * 1024, time_cost=2, parallelism=1)
# Hash de uma senha descartada: igualar o tempo de resposta quando o login não existe.
HASH_FALSO = HASHER.hash(secrets.token_urlsafe(16))


def hash_senha(senha: str) -> str:
    return HASHER.hash(senha)


def senha_confere(hash_guardado: str | None, senha: str) -> bool:
    """Verifica sempre (com hash falso se não há usuário) para não vazar existência por tempo."""
    try:
        return HASHER.verify(hash_guardado or HASH_FALSO, senha) and hash_guardado is not None
    except (VerificationError, InvalidHashError):
        return False


def novo_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> bytes:
    """O banco guarda só o SHA-256 do token do cookie; vazar a tabela não vaza sessões."""
    return hashlib.sha256(token.encode()).digest()


def tokens_iguais(a: str, b: str) -> bool:
    return secrets.compare_digest(a.encode(), b.encode())


class LimitadorLogin:
    """Janela deslizante de falhas por login, em memória (processo único local).

    Passado o limite, bloqueia até a falha mais antiga sair da janela, inclusive com a
    senha certa. Limitação aceita (ADR 038): reiniciar o processo zera o contador.
    """

    def __init__(
        self, max_falhas: int, janela_s: int, relogio: Callable[[], float] = time.monotonic
    ) -> None:
        self._max = max_falhas
        self._janela = janela_s
        self._relogio = relogio
        self._falhas: dict[str, deque[float]] = {}

    def _podar(self, chave: str) -> deque[float]:
        agora = self._relogio()
        fila = self._falhas.setdefault(chave, deque())
        while fila and agora - fila[0] >= self._janela:
            fila.popleft()
        if not fila:
            self._falhas.pop(chave, None)
        return fila

    def espera_s(self, chave: str) -> int:
        """Segundos até poder tentar de novo; 0 se liberado."""
        fila = self._podar(chave)
        if len(fila) < self._max:
            return 0
        return max(1, int(self._janela - (self._relogio() - fila[0])) + 1)

    def registrar_falha(self, chave: str) -> None:
        self._podar(chave)
        self._falhas.setdefault(chave, deque()).append(self._relogio())

    def limpar(self, chave: str) -> None:
        self._falhas.pop(chave, None)
