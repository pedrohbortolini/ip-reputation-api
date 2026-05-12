# Importamos as bibliotecas necessárias.
# O FastAPI é a mais importante — cria a aplicação web que recebe as requisições
# e chama as funções certas dependendo da URL acessada.
import ipaddress
from fastapi import FastAPI, HTTPException
from app.cache import TTLCache
from app.reputation import get_reputation, ExternalAPIError


# Criamos o objeto app a partir da classe FastAPI.
# Ele é a nossa aplicação web — é nele que registramos as rotas com @app.get(...)
app = FastAPI(title="IP Reputation API", version="1.0.0")

# Criamos o objeto cache a partir da classe TTLCache.
# Esse objeto fica vivo enquanto o container estiver rodando,
# guardando resultados por 1 hora (3600 segundos).
cache = TTLCache(ttl_seconds=3600)


# O @ indica pro FastAPI: "quando alguém acessar GET /health, execute a função abaixo."
@app.get("/health")
async def health():
    # Retorna apenas {"status": "ok"}.
    # O ALB bate aqui a cada 30s pra saber se o container está vivo.
    return {"status": "ok"}


# O @ indica pro FastAPI: "quando alguém acessar GET /reputation/{ip}, execute a função abaixo."
# O {ip} na URL é dinâmico — vira o parâmetro ip da função.
@app.get("/reputation/{ip}")
async def reputation(ip: str):

    # Valida se o que chegou é realmente um IP (IPv4 ou IPv6).
    # Se não for, retorna erro 400 imediatamente sem continuar.
    try:
        ipaddress.ip_address(ip)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"IP inválido: {ip}")

    # Verifica se esse IP já está no cache.
    # Se estiver, retorna o resultado salvo sem consultar as APIs externas.
    # O ** desempacota tudo do dicionário cached e adiciona "cached": True.
    cached = cache.get(ip)
    if cached is not None:
        return {**cached, "cached": True}

    # Se não estava no cache, consulta as APIs externas (AbuseIPDB e IPInfo).
    # Se as duas falharem, retorna erro 503 para o usuário.
    try:
        result = await get_reputation(ip)
    except ExternalAPIError as e:
        raise HTTPException(status_code=503, detail=str(e))

    # Salva o resultado no cache para a próxima consulta do mesmo IP.
    # Depois retorna a resposta para o usuário com "cached": False.
    cache.set(ip, result)
    return {**result, "cached": False}