FROM python:3.13-slim
WORKDIR /opt/braink
COPY deployment/braink_runtime_service.py /opt/braink/deployment/braink_runtime_service.py
COPY enterprise/FOUNDRY_REGISTRY_R21.json /opt/braink/enterprise/FOUNDRY_REGISTRY_R21.json
COPY enterprise/foundry_operations_r22.py /opt/braink/enterprise/foundry_operations_r22.py
RUN mkdir -p /var/lib/braink
EXPOSE 8799
HEALTHCHECK --interval=30s --timeout=3s --retries=3 CMD python -c "import json,urllib.request; assert json.load(urllib.request.urlopen('http://127.0.0.1:8799/health'))['status']=='PASS'"
CMD ["python","/opt/braink/deployment/braink_runtime_service.py","--state","/var/lib/braink/runtime_state.json","--operations-state","/var/lib/braink/foundary_operations_r22.json","--foundaries","/opt/braink/enterprise/FOUNDRY_REGISTRY_R21.json","--host","0.0.0.0","--port","8799"]
