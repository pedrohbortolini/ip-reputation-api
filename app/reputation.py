import os
import httpx


# Sem timeout, uma API travada derrubaria toda a aplicação.
TIMEOUT = httpx.Timeout(5.0)


class ExternalAPIError(Exception):
    """Erro ao consultar uma das APIs externas (AbuseIPDB ou IPInfo)."""
    pass


async def fetch_abuseipdb(ip: str) -> dict:
    """Consulta AbuseIPDB e retorna dados de reputação."""
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


async def fetch_ipinfo(ip: str) -> dict:
    """Consulta IPInfo e retorna dados de localização/provedor."""
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
    """
    Consulta ambas as APIs e consolida num único dicionário.
    Se uma falhar, retorna o que a outra trouxe + lista de erros.
    Se as duas falharem, levanta ExternalAPIError.
    """
    result = {"ip": ip, "abuseipdb": None, "ipinfo": None, "errors": []}

    try:
        result["abuseipdb"] = await fetch_abuseipdb(ip)
    except ExternalAPIError as e:
        result["errors"].append(str(e))

    try:
        result["ipinfo"] = await fetch_ipinfo(ip)
    except ExternalAPIError as e:
        result["errors"].append(str(e))

    if result["abuseipdb"] is None and result["ipinfo"] is None:
        raise ExternalAPIError("Todas as fontes externas falharam")

    return result
