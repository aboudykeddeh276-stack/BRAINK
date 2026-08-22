from urllib.parse import quote
from urllib.request import urlopen
import json, sys, time

LEXICAL=sys.argv[1]
ENDPOINTS=sys.argv[2:]
attempts=[]
for ep in ENDPOINTS:
    url=f"{ep}/resolve?lexical_id={quote(LEXICAL,safe='')}"
    t=time.perf_counter()
    try:
        with urlopen(url,timeout=1.5) as r:
            data=json.loads(r.read().decode())
        attempts.append({"endpoint":ep,"status":"PASS","latency_ms":(time.perf_counter()-t)*1000})
        print(json.dumps({"status":"PASS","selected_endpoint":ep,"attempts":attempts,"response":data},indent=2))
        raise SystemExit(0)
    except Exception as e:
        attempts.append({"endpoint":ep,"status":"FAIL","error":type(e).__name__})
print(json.dumps({"status":"FAIL","attempts":attempts},indent=2))
raise SystemExit(2)
