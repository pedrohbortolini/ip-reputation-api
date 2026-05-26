import ipaddress
from fastapi import FastAPI, HTTPException
from app.cache import TTLCache
from app.reputation import get_reputation, ExternalAPIError


app = FastAPI(title="IP Reputation API", version="1.0.0")

# Cache vive enquanto o container estiver de pé — 1h de TTL por IP.
cache = TTLCache(ttl_seconds=3600)


@app.get("/health")
async def health():
    # Endpoint propositalmente trivial — o ALB bate aqui a cada 30s
    # e não pode falhar por causa de uma API externa fora do ar.
    return {"status": "ok"}


@app.get("/reputation/{ip}")
async def reputation(ip: str):
    try:
        ipaddress.ip_address(ip)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"IP inválido: {ip}")

    cached = cache.get(ip)
    if cached is not None:
        return {**cached, "cached": True}

    try:
        result = await get_reputation(ip)
    except ExternalAPIError as e:
        raise HTTPException(status_code=503, detail=str(e))

    cache.set(ip, result)
    return {**result, "cached": False}
