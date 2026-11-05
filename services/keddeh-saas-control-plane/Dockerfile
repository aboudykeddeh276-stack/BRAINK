FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    KEDDEH_SAAS_DB=/data/keddeh_saas.sqlite3 \
    BRAINK_SAAS_STATE_DIR=/data/braink

WORKDIR /app

RUN useradd --system --uid 10001 --create-home appuser \
    && mkdir -p /data /tmp/keddeh-saas \
    && chown -R appuser:appuser /data /tmp/keddeh-saas

# The service consumes BRAINK's resident runtime implementation.  It does not
# carry a synthesized replacement of the IL-LLM ledger or runtime registry.
COPY runtime /app/runtime
COPY services/keddeh-saas-control-plane/pyproject.toml /tmp/keddeh-saas/pyproject.toml
COPY services/keddeh-saas-control-plane/src /tmp/keddeh-saas/src
RUN pip install --no-cache-dir /tmp/keddeh-saas

USER appuser
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=2)"

CMD ["uvicorn","keddeh_saas.app:app","--host","0.0.0.0","--port","8000","--workers","1"]
