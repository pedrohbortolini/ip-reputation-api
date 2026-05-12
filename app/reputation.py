# os: acessa recursos do sistema operacional (ex: variáveis de ambiente)
# httpx: faz requisições HTTP (chamar APIs externas)
# Optional (typing): indica que um valor pode ser do tipo X ou None
import os
import httpx
from typing import Optional


# Timeout de 5 segundos — se a API externa demorar mais que isso, desiste.
# Sem timeout, uma API travada derrubaria a aplicação inteira.
TIMEOUT = httpx.Timeout(5.0)

# Criamos uma classe que herda de Exception (erro padrão do Python),
# definindo um erro personalizado para usar no código quando sabemos que pode ocorrer falha em APIs externas.
# Em vez de usar um erro genérico, indicamos exatamente qual tipo de erro aconteceu.

class ExternalAPIError(Exception):
    """Exceção customizada pra quando as APIs externas falham."""
    pass

# Criamos uma função assíncrona (async), o que permite fazer chamadas externas sem travar a aplicação.
# Usamos a biblioteca "os" para pegar a API key do sistema (variável de ambiente, como em containers).
# Se não encontrar a key, lançamos o erro personalizado que criamos anteriormente.

async def fetch_abuseipdb(ip: str) -> dict:
    """Consulta AbuseIPDB e retorna dados de reputação."""
    api_key = os.getenv("ABUSEIPDB_KEY")
    if not api_key:
        raise ExternalAPIError("ABUSEIPDB_KEY não configurada")

    url = "https://api.abuseipdb.com/api/v2/check"
    headers = {"Key": api_key, "Accept": "application/json"}
    params = {"ipAddress": ip, "maxAgeInDays": 90}

 # O async with cria um cliente HTTP (httpx.AsyncClient) que abre a conexão e fecha automaticamente depois de usar.
 # Criamos a variável response que faz a requisição usando o client.
 #O client usa a url, headers (com a API key) e params (parâmetros da requisição).
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            response = await client.get(url, headers=headers, params=params)
            #response.raise_for_status() verifica se a resposta da API deu erro (ex: 400, 500)
            response.raise_for_status()
            #["data"] pega apenas a parte "data" do JSON retornado pela API
            data = response.json()["data"]
            #No return, criamos um novo dicionário com apenas os dados que queremos,
            #usando data.get() para evitar erro caso alguma chave não exista.
            return {
                "abuse_score": data.get("abuseConfidenceScore"),
                "total_reports": data.get("totalReports"),
                "country_code": data.get("countryCode"),
                "isp": data.get("isp"),
            }
        
        #No except, capturamos erros de HTTP da biblioteca httpx
        #e transformamos em um erro personalizado (ExternalAPIError),
        #incluindo a mensagem original do erro (e).
        except httpx.HTTPError as e:
            raise ExternalAPIError(f"AbuseIPDB falhou: {e}")

# Função assíncrona para consultar a API IPInfo (mesma lógica da AbuseIPDB).
# Usa f-string na URL para inserir o IP diretamente (https://ipinfo.io/{ip}).
# Diferente da outra API:
# - aqui a AP key vai em params (token), não em headers
# - a resposta JSON já vem direta (não precisa acessar ["data"])
# O restante segue o mesmo padrão

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

# Criamos uma função assíncrona chamada get_reputation com o objetivo de retornar
# um dicionário contendo as informações coletadas das APIs.
# No começo da função criamos o dicionário result:
# - ip guarda o IP consultado
# - abuseipdb e ipinfo começam como None aguardando os dados das APIs
# - errors começa como lista vazia para armazenar possíveis erros

# Depois abrimos blocos try utilizando as funções criadas anteriormente:
# fetch_abuseipdb e fetch_ipinfo.
# Essas funções consultam as APIs externas e retornam os dados encontrados.
# Caso aconteça ExternalAPIError, o erro é capturado e salvo dentro da lista errors,
# sem interromper a aplicação.


async def get_reputation(ip: str) -> dict:
    """
    Consulta ambas as APIs e consolida num único dicionário de resposta.
    Se uma das APIs falhar, deixa os campos dela como None mas retorna o que conseguiu.
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

    # Se as duas APIs falharam, considera erro total
    if result["abuseipdb"] is None and result["ipinfo"] is None:
        raise ExternalAPIError("Todas as fontes externas falharam")

    return result
