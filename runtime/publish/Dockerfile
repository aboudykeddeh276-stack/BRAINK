FROM python:3.13-slim
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
COPY scripts ./scripts
RUN pip install --no-cache-dir .
COPY seed_registry.json ./
RUN mkdir -p /data
ENV BRAINK_DATA_DIR=/data BRAINK_PORT=8000 KEX_STRIPE_SOCKET=/run/keddeh/kex-runner.sock
EXPOSE 8000
CMD ["uvicorn","braink_runtime.casepath_app:app","--host","0.0.0.0","--port","8000"]
