FROM python:3.13-slim
WORKDIR /app

COPY mcp/braink_process_adapter/requirements.txt /tmp/mcp-requirements.txt
RUN pip install --no-cache-dir -r /tmp/mcp-requirements.txt "fastapi>=0.115"

COPY enterprise ./enterprise
COPY mcp ./mcp
COPY runtime ./runtime

ENV PYTHONUNBUFFERED=1
ENV BRAINK_MCP_STATE_DIR=/data/braink_mcp
EXPOSE 8810

CMD ["uvicorn","runtime.mcp_sdk_environment_server:app","--host","0.0.0.0","--port","8810"]
