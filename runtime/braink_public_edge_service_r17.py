from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from pathlib import Path
import json, os, sys, hashlib

BLOCK=4096
BRAINK_OFF=256*BLOCK
SERVICE_OFF=768*BLOCK
MUTATION_OFF=1024*BLOCK

def sha(b): return hashlib.sha256(b).hexdigest()

def read_block(fd, off):
    h=os.pread(fd,8,off)
    if len(h)<8: return None
    n=int.from_bytes(h[:4],"big")
    if n<=0 or n>BLOCK-8: return None
    raw=os.pread(fd,n,off+8)
    return {"obj":json.loads(raw.decode()),"sha256":sha(raw)}

def load_machine(path):
    fd=os.open(path,os.O_RDONLY)
    root=read_block(fd,BRAINK_OFF)
    fabric=read_block(fd,SERVICE_OFF)
    state=read_block(fd,MUTATION_OFF)
    os.close(fd)
    if not root or not fabric:
        raise RuntimeError("E_MACHINE_NOT_READY")
    return root["obj"], fabric["obj"], (state["obj"] if state else {"revision":0,"objects":{}})

DISK=Path(sys.argv[1])
HOST=sys.argv[2] if len(sys.argv)>2 else "0.0.0.0"
PORT=int(sys.argv[3]) if len(sys.argv)>3 else 17941

EDGE_ID="BRAINK::PUBLIC_EDGE::R17"
EDGE_LEX="LEX://SERVER/BRAINK/PUBLIC_EDGE"

class H(BaseHTTPRequestHandler):
    def sendj(self,status,obj):
        raw=json.dumps(obj,sort_keys=True).encode()
        self.send_response(status)
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(raw)))
        self.send_header("X-BRAINK-Service",EDGE_ID)
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        try:
            root,fabric,state=load_machine(DISK)
            u=urlparse(self.path)
            q=parse_qs(u.query)
            base_receipt={
                "edge_id":EDGE_ID,
                "edge_lexical_id":EDGE_LEX,
                "machine_id":root["machine_id"],
                "braink_id":root["braink_id"],
                "lineage_root":root["lineage_root"],
                "listener":f"{HOST}:{PORT}",
                "external_binding_state":"UNBOUND_PUBLIC_AUTHORITY"
            }

            if u.path=="/health":
                return self.sendj(200,{**base_receipt,"status":"PASS","service":"PUBLIC_EDGE"})

            if u.path=="/systems":
                services={}
                for name,svc in fabric.get("services",{}).items():
                    services[name]={
                        "type":svc.get("type"),
                        "lexical_id":svc.get("lexical_id"),
                        "vector_id":svc.get("vector_id"),
                        "route_id":svc.get("route_id"),
                        "adapter":svc.get("adapter")
                    }
                return self.sendj(200,{**base_receipt,"status":"PASS","services":services})

            if u.path=="/dns":
                return self.sendj(200,{
                    **base_receipt,
                    "status":"PASS",
                    "authority":"INTERNAL_RESIDENT_NOT_PUBLIC_AUTHORITY",
                    "records":state.get("objects",{}).get("DNS",{})
                })

            if u.path=="/domain":
                name=q.get("name",["keddeh.com"])[0]
                domain_root=fabric.get("services",{}).get("DOMAIN_ROOT",{})
                if domain_root.get("domain_name")!=name:
                    return self.sendj(404,{**base_receipt,"status":"NOT_FOUND","domain":name})
                return self.sendj(200,{
                    **base_receipt,
                    "status":"PASS",
                    "domain":name,
                    "domain_root":domain_root,
                    "public_dns_authority":"NOT_BOUND",
                    "public_tls_authority":"NOT_BOUND",
                    "registry_authority":"NOT_BOUND"
                })

            if u.path=="/cloud/object":
                oid=q.get("id",[""])[0]
                obj=state.get("objects",{}).get("CLOUD",{}).get(oid)
                if obj is None:
                    return self.sendj(404,{**base_receipt,"status":"NOT_FOUND","object_id":oid})
                return self.sendj(200,{**base_receipt,"status":"PASS","object":obj})

            return self.sendj(404,{**base_receipt,"status":"NOT_FOUND","path":u.path})
        except Exception as e:
            return self.sendj(500,{"status":"FAIL","service":"PUBLIC_EDGE","error":str(e)})

    def log_message(self,*args): pass

print(json.dumps({
    "status":"LISTENING",
    "service":"PUBLIC_EDGE",
    "edge_id":EDGE_ID,
    "edge_lexical_id":EDGE_LEX,
    "host":HOST,
    "port":PORT,
    "machine_disk":str(DISK)
}),flush=True)
ThreadingHTTPServer((HOST,PORT),H).serve_forever()
