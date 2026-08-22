from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs
import json, hashlib, os, sys

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

def write_block(fd, off, obj):
    raw=json.dumps(obj,sort_keys=True,separators=(",",":")).encode()
    if len(raw)>BLOCK-8: raise RuntimeError("E_BLOCK_TOO_LARGE")
    buf=bytearray(BLOCK)
    buf[:4]=len(raw).to_bytes(4,"big")
    buf[8:8+len(raw)]=raw
    os.pwrite(fd,bytes(buf),off)
    return sha(raw)

def load(path):
    fd=os.open(path,os.O_RDONLY)
    root=read_block(fd,BRAINK_OFF)
    fabric=read_block(fd,SERVICE_OFF)
    mutations=read_block(fd,MUTATION_OFF)
    os.close(fd)
    if not root or not fabric: raise RuntimeError("E_MACHINE_NOT_READY")
    return root["obj"],fabric["obj"],mutations["obj"] if mutations else {"revision":0,"objects":{}}

def save_mutations(path,state):
    fd=os.open(path,os.O_RDWR)
    d=write_block(fd,MUTATION_OFF,state)
    os.fsync(fd); os.close(fd)
    return d

DISK=Path(sys.argv[1]); HOST=sys.argv[2]; PORT=int(sys.argv[3])

LEX_MAP={
  "LEX://SERVER/GLOBAL":"SERVER_ROOT",
  "LEX://DOMAIN/keddeh.com":"DOMAIN_ROOT",
  "LEX://DNS/keddeh.com":"DNS_ROOT",
  "LEX://REGISTRAR/keddeh.com":"REGISTRAR_ROOT",
  "LEX://TLS/keddeh.com":"TLS_ROOT",
  "LEX://CLOUD/BRAINK/GLOBAL":"CLOUD_ROOT",
}

class H(BaseHTTPRequestHandler):
    def sendj(self,status,obj):
        raw=json.dumps(obj,sort_keys=True).encode()
        self.send_response(status)
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        try:
            root,fabric,state=load(DISK)
            u=urlparse(self.path); q=parse_qs(u.query)
            if u.path=="/health":
                return self.sendj(200,{"status":"PASS","machine_id":root["machine_id"],"braink_id":root["braink_id"],"lineage_root":root["lineage_root"]})
            if u.path=="/resolve":
                lexical=q.get("lexical_id",[""])[0]
                k=LEX_MAP.get(lexical)
                if not k: return self.sendj(404,{"status":"NOT_FOUND","lexical_id":lexical})
                return self.sendj(200,{"status":"PASS","machine_id":root["machine_id"],"lineage_root":root["lineage_root"],"root":k,"service":fabric["services"][k]})
            if u.path=="/cloud/read":
                oid=q.get("object_id",[""])[0]
                obj=state["objects"].get("CLOUD",{}).get(oid)
                if obj is None: return self.sendj(404,{"status":"NOT_FOUND","object_id":oid})
                return self.sendj(200,{"status":"PASS","machine_id":root["machine_id"],"object":obj})
            if u.path=="/dns/read":
                return self.sendj(200,{"status":"PASS","machine_id":root["machine_id"],"records":state["objects"].get("DNS",{})})
            if u.path=="/registrar/read":
                return self.sendj(200,{"status":"PASS","machine_id":root["machine_id"],"registrar_state":state["objects"].get("REGISTRAR",{})})
            if u.path=="/tls/read":
                return self.sendj(200,{"status":"PASS","machine_id":root["machine_id"],"tls_state":state["objects"].get("TLS",{})})
            return self.sendj(404,{"status":"NOT_FOUND"})
        except Exception as e:
            return self.sendj(500,{"status":"FAIL","error":str(e)})

    def do_POST(self):
        try:
            root,fabric,state=load(DISK)
            n=int(self.headers.get("Content-Length","0"))
            body=json.loads(self.rfile.read(n) or b"{}")
            u=urlparse(self.path)
            state.setdefault("objects",{})
            if u.path=="/cloud/write":
                oid=body["object_id"]; payload=body["payload"]
                obj={"object_id":oid,"payload":payload,"payload_sha256":sha(payload.encode()),"lexical_id":f"LEX://CLOUD/OBJECT/{oid}","state":"COMMITTED"}
                state["objects"].setdefault("CLOUD",{})[oid]=obj
            elif u.path=="/dns/update":
                if body.get("authority")!="INTERNAL":
                    return self.sendj(403,{"status":"BLOCKED","reason":"PUBLIC_AUTHORITY_NOT_PRESENT"})
                state["objects"].setdefault("DNS",{})[body["name"]]={"value":body["value"],"authority":"INTERNAL_RESIDENT_NOT_PUBLIC_AUTHORITY"}
            elif u.path=="/registrar/update":
                if body.get("authority")!="INTERNAL":
                    return self.sendj(403,{"status":"BLOCKED","reason":"REGISTRY_AUTHORITY_NOT_PRESENT"})
                state["objects"].setdefault("REGISTRAR",{})["keddeh.com"]={"lock":bool(body.get("lock",True)),"authority":"INTERNAL_RESIDENT_NOT_REGISTRY_AUTHORITY"}
            elif u.path=="/tls/update":
                if body.get("authority")!="INTERNAL":
                    return self.sendj(403,{"status":"BLOCKED","reason":"CA_AUTHORITY_NOT_PRESENT"})
                state["objects"].setdefault("TLS",{})["keddeh.com"]={"mode":body.get("mode","PENDING_EXTERNAL_CA"),"authority":"INTERNAL_RESIDENT_NOT_CA_ISSUED"}
            else:
                return self.sendj(404,{"status":"NOT_FOUND"})
            state["revision"]=int(state.get("revision",0))+1
            state["last_writer_machine"]=root["machine_id"]
            digest=save_mutations(DISK,state)
            return self.sendj(200,{"status":"PASS","machine_id":root["machine_id"],"revision":state["revision"],"mutation_sha256":digest})
        except Exception as e:
            return self.sendj(500,{"status":"FAIL","error":str(e)})

    def log_message(self,*a): pass

print(json.dumps({"status":"LISTENING","machine_disk":str(DISK),"host":HOST,"port":PORT}),flush=True)
ThreadingHTTPServer((HOST,PORT),H).serve_forever()
