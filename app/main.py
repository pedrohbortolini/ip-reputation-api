import ipaddress

from fastapi import FastAPI, HTTPException

from app.cache import TTLCache
from app.reputation import get_reputation, ExternalAPIError
from app.metrics import (
    prometheus_middleware,
    metrics_endpoint,
    cache_hits_total,
    cache_misses_total,
    cache_size,
)


app = FastAPI(title="IP Reputation API", version="1.0.0")

app.middleware("http")(prometheus_middleware)

cache = TTLCache(ttl_seconds=3600)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/reputation/{ip}")
async def reputation(ip: str):
    try:
        ipaddress.ip_address(ip)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"IP inválido: {ip}")

    cached = cache.get(ip)
    if cached is not None:
        cache_hits_total.inc()
        return {**cached, "cached": True}

    cache_misses_total.inc()

    try:
        result = await get_reputation(ip)
    except ExternalAPIError as e:
        raise HTTPException(status_code=503, detail=str(e))

    cache.set(ip, result)
    cache_size.set(len(cache._store))

    return {**result, "cached": False}


app.add_route("/metrics", metrics_endpoint)
