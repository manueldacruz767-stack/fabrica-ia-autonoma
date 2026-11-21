FROM python:3.11-slim AS construtor

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /construcao
COPY requirements-app.txt ./
RUN python -m pip install --no-cache-dir --prefix=/instalado -r requirements-app.txt

FROM python:3.11-slim AS execucao

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HIS_HOST=0.0.0.0 \
    HIS_PORT=8000 \
    HIS_DB_PATH=/dados/his.db

WORKDIR /app

RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin appuser \
    && mkdir -p /dados \
    && chown appuser:appuser /dados

COPY --from=construtor /instalado /usr/local
COPY --chown=appuser:appuser requirements-app.txt ./
COPY --chown=appuser:appuser run_app.py ./
COPY --chown=appuser:appuser app ./app

USER appuser
VOLUME ["/dados"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.getenv('HIS_PORT', '8000') + '/health', timeout=3)"

CMD ["python", "run_app.py"]
