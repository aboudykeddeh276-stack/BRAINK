from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
import json, os, hashlib, sys

BLOCK=4096
SUPER_OFF=0
BRAINK_OFF=256*BLOCK
SERVICE_OFF=768*BLOCK

def sha(b): return hashlib.sha256(b).hexdigest()

def read_block(fd, off):
    head=os.pread(fd,8,off)
    if len(head)<8: return None
    n=int.from_bytes(head[:4],"big")
    if n<=0 or n>BLOCK-8: return None
    raw=os.pread(fd,n,off+8)
    return {"obj":json.loads(raw.decode()),"sha256":sha(raw)}

def load_machine(path):
    fd=os.open(path,os.O_RDONLY)
    root=read_block(fd,BRAINK_OFF)
    fabric=read_block(fd,SERVICE_OFF)
    os.close(fd)
    if not root or not fabric: raise RuntimeError("E_MACHINE_NOT_READY")
    return root["obj"], fabric["obj"], fabric["sha256"]

DISK=Path(sys.argv[1])
HOST=sys.argv[2]
PORT=int(sys.argv[3])

class H(BaseHTTPRequestHandler):
    def _send(self,status,obj):
        raw=json.dumps(obj,sort_keys=True).encode()
        self.send_response(status)
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        try:
            root,fabric,fhash=load_machine(DISK)
            if self.path=="/health":
                return self._send(200,{
                    "status":"PASS",
                    "machine_id":root["machine_id"],
                    "braink_id":root["braink_id"],
                    "lineage_root":root["lineage_root"],
                    "fabric_sha256":fhash,
                    "listener_contract":f"0.0.0.0:{PORT}",
                })
            if self.path.startswith("/resolve?"):
                from urllib.parse import urlparse, parse_qs
                q=parse_qs(urlparse(self.path).query)
                lexical=q.get("lexical_id",[""])[0]
                hits=[]
                for name,svc in fabric["services"].items():
                    if svc.get("lexical_id")==lexical:
                        hits.append({"root":name,**svc})
                if not hits:
                    return self._send(404,{"status":"NOT_FOUND","lexical_id":lexical})
                return self._send(200,{
                    "status":"PASS",
                    "machine_id":root["machine_id"],
                    "braink_id":root["braink_id"],
                    "lineage_root":root["lineage_root"],
                    "lexical_id":lexical,
                    "results":hits,
                    "fabric_sha256":fhash,
                })
            return self._send(404,{"status":"NOT_FOUND"})
        except Exception as e:
            return self._send(500,{"status":"FAIL","error":str(e)})

    def log_message(self, fmt, *args):
        pass

httpd=ThreadingHTTPServer((HOST,PORT),H)
print(json.dumps({"status":"LISTENING","disk":str(DISK),"host":HOST,"port":PORT}),flush=True)
httpd.serve_forever()
