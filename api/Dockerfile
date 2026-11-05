# syntax=docker/dockerfile:1.7
# Imagem da API única do EnadeX (EnadeX_Backend/api_main.py: MultiENADE, EduCluster, E-XplainENADE e ENADE-Time).
# Contexto de build: raiz do EnadeX_Infra, com o backend em ./backend (o CI faz o checkout).
FROM python:3.13-slim

# MALLOC_ARENA_MAX=2: o glibc cria uma arena de memória por thread, e as rotas rodam no threadpool do FastAPI. Com
# pandas/numpy, isso fragmenta a memória e infla o consumo do processo; duas arenas bastam.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    MPLBACKEND=Agg \
    MPLCONFIGDIR=/tmp/matplotlib \
    NUMBA_CACHE_DIR=/tmp/numba \
    MALLOC_ARENA_MAX=2

# fonts-liberation: o relatório em PDF do E-XplainENADE usa a Liberation Sans (e_xplainenade/packages.txt).
# libgomp1: OpenMP para scikit-learn e numba. appuser: a API não roda como root.
RUN apt-get update \
 && apt-get install -y --no-install-recommends fonts-liberation libgomp1 \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --create-home --uid 10001 appuser

WORKDIR /app

# Dependências primeiro: esta camada (a mais pesada) só é refeita quando o requirements muda.
COPY api/requirements.txt /opt/enadex/requirements.txt
RUN pip install -r /opt/enadex/requirements.txt \
 && pip freeze > /opt/enadex/requirements.lock

COPY --chmod=0755 api/entrypoint.sh api/warmup.py /opt/enadex/

# O código já entra com o dono certo (um chown -R depois duplicaria a camada inteira). As pastas onde os módulos
# gravam em tempo de execução são criadas aqui para que o volume nomeado herde o dono: educluster/.cache (descrições
# por IA; o parquet dali só vale para a origem local) e e_xplainenade/local/outputs (PDFs; vira tmpfs no compose).
COPY --chown=appuser:appuser backend/ /app/
RUN chown appuser:appuser /app \
 && install -d -o appuser -g appuser /app/educluster/.cache /app/e_xplainenade/local /app/e_xplainenade/local/outputs

USER appuser
EXPOSE 8000
ENTRYPOINT ["/opt/enadex/entrypoint.sh"]
