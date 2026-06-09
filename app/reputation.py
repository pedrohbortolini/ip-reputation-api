import os
import time

import httpx

from app.metrics import (
    external_api_requests_total,
    external_api_duration_seconds,
)


TIMEOUT = httpx.Timeout(5.0)


class ExternalAPIError(Exception):
    pass


async def _instrumented_call(api_name: str, fetch_fn, *args, **kwargs):
    start = time.perf_counter()
    try:
        result = await fetch_fn(*args, **kwargs)
        external_api_requests_total.labels(api=api_name, status="success").inc()
        return result
    except Exception:
        external_api_requests_total.labels(api=api_name, status="error").inc()
        raise
    finally:
        duration = time.perf_counter() - start
        external_api_duration_seconds.labels(api=api_name).observe(duration)


async def _fetch_abuseipdb(ip: str) -> dict:
    api_key = os.getenv("ABUSEIPDB_KEY")
    if not api_key:
        raise ExternalAPIError("ABUSEIPDB_KEY não configurada")

    url = "https://api.abuseipdb.com/api/v2/check"
    headers = {"Key": api_key, "Accept": "application/json"}
    params = {"ipAddress": ip, "maxAgeInDays": 90}

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()["data"]
            return {
                "abuse_score": data.get("abuseConfidenceScore"),
                "total_reports": data.get("totalReports"),
                "country_code": data.get("countryCode"),
                "isp": data.get("isp"),
            }
        except httpx.HTTPError as e:
            raise ExternalAPIError(f"AbuseIPDB falhou: {e}")


async def _fetch_ipinfo(ip: str) -> dict:
    api_key = os.getenv("IPINFO_KEY")
    if not api_key:
        raise ExternalAPIError("IPINFO_KEY não configurada")

    url = f"https://ipinfo.io/{ip}"
    params = {"token": api_key}

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            return {
                "country": data.get("country"),
                "city": data.get("city"),
                "org": data.get("org"),
                "hostname": data.get("hostname"),
            }
        except httpx.HTTPError as e:
            raise ExternalAPIError(f"IPInfo falhou: {e}")


async def get_reputation(ip: str) -> dict:
    result = {"ip": ip, "abuseipdb": None, "ipinfo": None, "errors": []}

    try:
        result["abuseipdb"] = await _instrumented_call("abuseipdb", _fetch_abuseipdb, ip)
    except ExternalAPIError as e:
        result["errors"].append(str(e))

    try:
        result["ipinfo"] = await _instrumented_call("ipinfo", _fetch_ipinfo, ip)
    except ExternalAPIError as e:
        result["errors"].append(str(e))

    if result["abuseipdb"] is None and result["ipinfo"] is None:
        raise ExternalAPIError("Todas as fontes externas falharam")

    return result
