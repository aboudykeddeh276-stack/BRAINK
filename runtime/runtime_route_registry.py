from pathlib import Path
import copy

SYSTEM_PYTHON="/usr/bin/python3"
DEFAULT_ROUTES={
 "qualification-http":{"runtime_id":"runtime://qualification-http","runtime_class":"HTTP_SERVICE","argv":[SYSTEM_PYTHON,"-m","http.server","18991","--bind","127.0.0.1"],"dependencies":[],"health_endpoint":"http://127.0.0.1:18991/"},
 "public-gateway":{"runtime_id":"runtime://public-gateway","runtime_class":"HTTP_SERVICE","argv":[SYSTEM_PYTHON,"runtime/public_gateway.py"],"dependencies":[],"health_endpoint":"http://127.0.0.1:8799/health"},
 "r23-closure":{"runtime_id":"runtime://r23-closure","runtime_class":"HTTP_SERVICE","argv":[SYSTEM_PYTHON,"deployment/r23_foundry_closure_service.py","--state","runtime/r23-closure.sqlite3"],"dependencies":[],"health_endpoint":"http://127.0.0.1:8800/closure/health"},
 "antigravity-deploy":{"runtime_id":"runtime://braink/antigravity-deploy/1","runtime_class":"ONE_SHOT_JOB","argv":[SYSTEM_PYTHON,"deploy/braink-public/deploy_antigravity_live.py"],"dependencies":["braink://local/orchestrator","vfs://kex/root","KEX://SERVER/PUBLIC-GATEWAY"],"health_endpoint":None,"timeout_seconds":600},
 "resident-execution-service":{"runtime_id":"runtime://braink/resident-execution-service/1","runtime_class":"UNIX_SERVICE","argv":[SYSTEM_PYTHON,"deployment/braink_execution_service.py"],"dependencies":["enterprise/orchestration/durable_execution_r5.py","enterprise/orchestration/resident_execution_fabric.py"],"health_endpoint":"unix:///tmp/braink-execution.sock"}
}
class RuntimeRouteRegistry:
 def __init__(self,root="."):self.root=Path(root)
 def resolve(self,route):
  if route not in DEFAULT_ROUTES:raise KeyError(route)
  return copy.deepcopy(DEFAULT_ROUTES[route])
 def routes(self):return sorted(DEFAULT_ROUTES)
