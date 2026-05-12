# ============================================
# Stage 1: Builder — instala dependências
# ============================================
# Existe apenas durante o build para instalar as dependências.
# Depois que a imagem final é criada, esse stage é descartado.
FROM python:3.12-slim AS builder

WORKDIR /build

# Copia o requirements.txt antes do código para aproveitar o cache do Docker.
# O Docker guarda um hash de cada arquivo — se o requirements.txt não mudou,
# ele pula o pip install e vai direto pra próxima etapa.
COPY requirements.txt .

# Instala as dependências em /install (pasta separada)
# para copiar só elas pro stage final, sem trazer as ferramentas de instalação.
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ============================================
# Stage 2: Runtime — imagem final
# ============================================
# Começa do zero com uma imagem limpa. O Stage 1 não existe mais aqui.
# Tudo que copiamos pro Stage 2 é o que vai estar dentro do container.
FROM python:3.12-slim

# Cria um usuário comum sem privilégios de administrador.
# O container vai rodar como esse usuário em vez de root.
RUN useradd --create-home --shell /bin/bash appuser

WORKDIR /app

# Copia só as dependências instaladas do Stage 1.
# As ferramentas de instalação ficam pra trás — imagem menor e mais segura.
COPY --from=builder /install /usr/local

# Copia o código da aplicação e define o appuser como dono dos arquivos.
# Sem isso os arquivos pertenceriam ao root e o appuser não poderia usá-los.
COPY --chown=appuser:appuser app/ ./app/

# Ativa o usuário sem privilégios. A partir daqui tudo roda como appuser.
USER appuser

# Documenta que o container usa a porta 8000.
EXPOSE 8000

# O Docker bate em /health a cada 30s para verificar se o container está vivo.
# Se falhar 3 vezes seguidas, o container é marcado como unhealthy.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health').raise_for_status()" || exit 1

# Comando executado quando o container inicia.
# Inicia o Uvicorn que carrega o FastAPI e fica escutando a porta 8000.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]