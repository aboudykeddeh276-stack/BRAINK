FROM python:3.13-slim
WORKDIR /opt/braink
COPY deployment/braink_runtime_service.py /opt/braink/deployment/braink_runtime_service.py
RUN mkdir -p /var/lib/braink
EXPOSE 8799
CMD ["python","/opt/braink/deployment/braink_runtime_service.py","--state","/var/lib/braink/runtime_state.json","--host","0.0.0.0","--port","8799"]
