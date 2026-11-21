FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HIS_HOST=0.0.0.0 \
    HIS_PORT=8000 \
    HIS_DB_PATH=/dados/his.db

WORKDIR /app

RUN useradd --create-home --shell /bin/bash appuser \
    && mkdir -p /dados \
    && chown -R appuser:appuser /dados

COPY requirements-app.txt ./
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r requirements-app.txt

COPY --chown=appuser:appuser . .

USER appuser
VOLUME ["/dados"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.getenv('HIS_PORT', '8000') + '/health', timeout=3)"

CMD ["python", "run_app.py"]
