import time
from typing import Callable

from fastapi import Request, Response
from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    CONTENT_TYPE_LATEST,
    generate_latest,
)


http_requests_total = Counter(
    "http_requests_total",
    "Total de requests HTTP",
    ["method", "route", "status"],
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "Duração das requests HTTP em segundos",
    ["method", "route"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)


cache_hits_total = Counter(
    "ip_reputation_cache_hits_total",
    "Total de cache hits",
)
cache_misses_total = Counter(
    "ip_reputation_cache_misses_total",
    "Total de cache misses",
)

cache_size = Gauge(
    "ip_reputation_cache_size",
    "Numero de entradas atualmente no cache",
)


external_api_requests_total = Counter(
    "external_api_requests_total",
    "Total de requests para APIs externas",
    ["api", "status"],
)

external_api_duration_seconds = Histogram(
    "external_api_duration_seconds",
    "Latência das chamadas a APIs externas",
    ["api"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)


async def prometheus_middleware(request: Request, call_next: Callable) -> Response:
    route = request.scope.get("route")
    route_path = route.path if route else request.url.path

    start = time.perf_counter()
    response = await call_next(request)
    duration = time.perf_counter() - start

    http_requests_total.labels(
        method=request.method,
        route=route_path,
        status=str(response.status_code),
    ).inc()

    http_request_duration_seconds.labels(
        method=request.method,
        route=route_path,
    ).observe(duration)

    return response


async def metrics_endpoint(request: Request) -> Response:
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )
