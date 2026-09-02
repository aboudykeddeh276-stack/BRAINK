from pathlib import Path
import copy
SYSTEM_PYTHON="/usr/bin/python3"
DEFAULT_ROUTES={
 "qualification-http":{"runtime_id":"runtime://qualification-http","runtime_class":"HTTP_SERVICE","argv":[SYSTEM_PYTHON,"-m","http.server","18991","--bind","127.0.0.1"],"dependencies":[],"health_endpoint":"http://127.0.0.1:18991/"},
 "public-gateway":{"runtime_id":"runtime://public-gateway","runtime_class":"HTTP_SERVICE","argv":[SYSTEM_PYTHON,"runtime/public_gateway.py"],"dependencies":[],"health_endpoint":"http://127.0.0.1:8799/health"},
 "r23-closure":{"runtime_id":"runtime://r23-closure","runtime_class":"HTTP_SERVICE","argv":[SYSTEM_PYTHON,"deployment/r23_foundry_closure_service.py","--state","runtime/r23-closure.sqlite3"],"dependencies":[],"health_endpoint":"http://127.0.0.1:8800/closure/health"}
}
class RuntimeRouteRegistry:
 def __init__(self,root="."):self.root=Path(root)
 def resolve(self,route):
  if route not in DEFAULT_ROUTES:raise KeyError(route)
  return copy.deepcopy(DEFAULT_ROUTES[route])
 def routes(self):return sorted(DEFAULT_ROUTES)
