from __future__ import annotations
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json,time
START=time.time();COUNTS={"requests":0}
class H(BaseHTTPRequestHandler):
    def _send(self,status,body,ctype="application/json"):
        raw=body.encode();self.send_response(status);self.send_header("Content-Type",ctype);self.send_header("Content-Length",str(len(raw)));self.end_headers();self.wfile.write(raw)
    def do_GET(self):
        COUNTS["requests"]+=1
        if self.path=="/health":return self._send(200,json.dumps({"status":"OK","service":"BRAINK_RUNTIME_INGRESS"}))
        if self.path=="/metrics":
            body="# TYPE braink_runtime_requests_total counter\nbraink_runtime_requests_total %s\n# TYPE braink_runtime_uptime_seconds gauge\nbraink_runtime_uptime_seconds %.3f\n"%(COUNTS["requests"],time.time()-START)
            return self._send(200,body,"text/plain; version=0.0.4")
        return self._send(404,json.dumps({"status":"NOT_FOUND"}))
    def log_message(self,*_):pass
def serve(host="127.0.0.1",port=19420):ThreadingHTTPServer((host,port),H).serve_forever()
if __name__=="__main__":serve()
