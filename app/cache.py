import time
from typing import Any, Optional


class TTLCache:
    """
    Cache simples em memória com TTL (time-to-live).
    Guarda um dicionário onde cada chave tem um valor + timestamp de expiração.
    Quando você busca uma chave, se o timestamp já passou, retorna None (como se não existisse).
    """

    def __init__(self, ttl_seconds: int = 3600):
        self._store: dict[str, tuple[Any, float]] = {}
        self._ttl = ttl_seconds

    def get(self, key: str) -> Optional[Any]:
        entry = self._store.get(key)
        if entry is None:
            return None

        value, expires_at = entry
        if time.time() > expires_at:
            # Expirou — remove e retorna None
            del self._store[key]
            return None

        return value

    def set(self, key: str, value: Any) -> None:
        expires_at = time.time() + self._ttl
        self._store[key] = (value, expires_at)
