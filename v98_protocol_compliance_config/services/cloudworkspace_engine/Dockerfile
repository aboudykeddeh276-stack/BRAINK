FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    DATA_DIR=/data \
    DATABASE_PATH=/data/cloudworkspace.db

RUN groupadd --system --gid 10001 keddeh \
    && useradd --system --uid 10001 --gid 10001 --home-dir /app --shell /usr/sbin/nologin keddeh \
    && mkdir -p /app /data \
    && chown -R 10001:10001 /app /data

WORKDIR /app
COPY --chown=10001:10001 server.py /app/server.py

USER 10001:10001
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=2).read()"

ENTRYPOINT ["python", "/app/server.py"]
