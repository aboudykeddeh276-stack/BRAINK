FROM python:3.13-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 KEDDEH_SAAS_DB=/data/keddeh_saas.sqlite3
WORKDIR /app
RUN useradd --system --uid 10001 --create-home appuser && mkdir -p /data && chown appuser:appuser /data
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=2)"
CMD ["uvicorn","keddeh_saas.app:app","--host","0.0.0.0","--port","8000","--workers","1"]
