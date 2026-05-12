import time
from typing import Any, Optional


class TTLCache:
    """
    Cache simples em memória com TTL (time-to-live).
    Guarda um dicionário onde cada chave tem um valor + timestamp de expiração.
    Quando você busca uma chave, se o timestamp já passou, retorna None (como se não existisse).
    """

# Método construtor da classe.
# Define o TTL (time to live) padrão como 3600 segundos (1 hora), caso não seja informado.
# Inicializa o atributo _store como um dicionário vazio, onde:
#   - a chave é uma string (str)
#   - o valor é uma tupla (qualquer valor, float)
# Também salva o TTL no atributo _ttl.
    def __init__(self, ttl_seconds: int = 3600):
        self._store: dict[str, tuple[Any, float]] = {}
        self._ttl = ttl_seconds

#Método para buscar um valor no dicionário _store usando uma chave (key).
#Usa o método get do dicionário para tentar encontrar a chave informada.
#Se a chave não existir, retorna None.
#Caso exista, armazena o valor na variável entry

    def get(self, key: str) -> Optional[Any]:
        entry = self._store.get(key)
        if entry is None:
            return None

# Desempacota o valor armazenado na variável entry em:
# - value: o dado salvo
# - expires_at: o tempo de expiração
# Verifica se o tempo atual (time.time()) é maior que o tempo de expiração
# Se for, significa que o valor expirou
# Nesse caso, remove a chave do dicionário e retorna None

        value, expires_at = entry
        if time.time() > expires_at:
            # Expirou — remove e retorna None
            del self._store[key]
            return None

        return value

# Método para adicionar um valor ao cache (_store) usando uma chave (key).
# Calcula o tempo de expiração somando o tempo atual (time.time()) com o TTL (_ttl).
# Armazena no dicionário a chave associada a uma tupla:
# (valor, tempo_de_expiracao)

    def set(self, key: str, value: Any) -> None:
        expires_at = time.time() + self._ttl
        self._store[key] = (value, expires_at)