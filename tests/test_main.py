# Mock é fingir partes do sistema durante os testes,
# evitando chamar APIs reais.
from unittest.mock import patch, AsyncMock

# TestClient é um client HTTP falso que simula requisições
# para o FastAPI sem precisar subir um servidor real.
from fastapi.testclient import TestClient

# Importa o objeto app (FastAPI) e o cache do projeto.
from app.main import app, cache


# Cria o client falso utilizando o app real.
client = TestClient(app)


# O pytest executa setup_function antes de cada teste.
# Aqui limpamos o cache para um teste não interferir no outro.
def setup_function():
    cache._store.clear()


# O pytest procura funções que começam com "test_".
# Normalmente o nome descreve o que está sendo testado
# e qual o resultado esperado.
def test_health_returns_200():
    """Health check deve sempre retornar 200 com status ok."""

    # Simula uma requisição GET para /health
    response = client.get("/health")

    # assert verifica se a comparação é verdadeira.
    # Se for falsa, o teste falha.
    assert response.status_code == 200

    # Verifica se o JSON retornado é exatamente o esperado.
    assert response.json() == {"status": "ok"}


# Envia um texto inválido como IP e verifica se retorna 400.
# A segunda verificação confirma se a mensagem contém "inválido".
def test_invalid_ip_returns_400():
    """IP com formato inválido deve retornar 400."""

    response = client.get("/reputation/nao-sou-um-ip")

    assert response.status_code == 400
    assert "inválido" in response.json()["detail"].lower()


# Mesmo teste acima, mas usando um IP numérico inválido.
def test_another_invalid_ip_returns_400():

    response = client.get("/reputation/999.999.999.999")

    assert response.status_code == 400


# patch substitui temporariamente a função real get_reputation.
# AsyncMock é usado porque a função original é async.
@patch("app.main.get_reputation", new_callable=AsyncMock)

# O mock criado pelo patch é passado automaticamente
# como parâmetro da função de teste.
def test_cache_hit_skips_external_call(mock_get_reputation):
    """
    Testa se o cache funciona corretamente:

    - Primeira chamada:
      consulta a função externa (mockada)
      e retorna cached=False

    - Segunda chamada:
      retorna do cache com cached=True
      sem chamar a função externa novamente
    """

    # Resposta falsa simulando a resposta real da API.
    fake_response = {
        "ip": "8.8.8.8",
        "abuseipdb": {"abuse_score": 0},
        "ipinfo": {"country": "US"},
        "errors": [],
    }

    # Quando get_reputation for chamado,
    # o mock retornará fake_response.
    mock_get_reputation.return_value = fake_response

    # Primeira chamada:
    # deve consultar a função externa.
    r1 = client.get("/reputation/8.8.8.8")

    assert r1.status_code == 200

    # Como foi a primeira vez,
    # ainda não veio do cache.
    assert r1.json()["cached"] is False

    # Verifica quantas vezes o mock foi chamado.
    # Aqui deve ser 1.
    assert mock_get_reputation.call_count == 1

    # Segunda chamada do mesmo IP:
    # agora deve retornar do cache.
    r2 = client.get("/reputation/8.8.8.8")

    assert r2.status_code == 200
    assert r2.json()["cached"] is True

    # Continua 1 porque não chamou
    # a função externa novamente.
    assert mock_get_reputation.call_count == 1