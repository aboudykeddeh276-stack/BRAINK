FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 ILLLM_ROOT=/data ILLLM_STATE=/state
RUN groupadd --system illlm && useradd --system --gid illlm --home /app illlm
WORKDIR /app
COPY illlm_runtime.py /app/illlm_runtime.py
RUN mkdir -p /data /state && chown -R illlm:illlm /app /data /state
USER illlm
ENTRYPOINT ["python","/app/illlm_runtime.py"]
CMD ["health"]
