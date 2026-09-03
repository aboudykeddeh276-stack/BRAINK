#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,os,socket,ssl,struct
from pathlib import Path
from registrar_core import Registrar

class RegistryAuthorityError(RuntimeError): pass
class EPPTransport:
 def __init__(self,host,port=700,cert=None,key=None,ca=None,timeout=10):
  self.host=host;self.port=int(port);self.cert=cert;self.key=key;self.ca=ca;self.timeout=timeout
 def _context(self):
  if not self.cert or not self.key: raise RegistryAuthorityError('EPP_CLIENT_CERTIFICATE_REQUIRED')
  ctx=ssl.create_default_context(cafile=self.ca or None);ctx.load_cert_chain(self.cert,self.key);ctx.minimum_version=ssl.TLSVersion.TLSv1_2;return ctx
 def connect(self):
  raw=socket.create_connection((self.host,self.port),self.timeout);return self._context().wrap_socket(raw,server_hostname=self.host)
 @staticmethod
 def recv_frame(sock):
  hdr=b''
  while len(hdr)<4:
   b=sock.recv(4-len(hdr))
   if not b:raise ConnectionError('EPP_EOF')
   hdr+=b
  n=struct.unpack('!I',hdr)[0]
  if n<5 or n>8*1024*1024:raise ValueError('INVALID_EPP_FRAME_LENGTH')
  data=b''
  while len(data)<n-4:
   b=sock.recv(n-4-len(data))
   if not b:raise ConnectionError('EPP_EOF')
   data+=b
  return data.decode('utf-8','replace')
 @staticmethod
 def send_frame(sock,xml):
  b=xml.encode();sock.sendall(struct.pack('!I',len(b)+4)+b)
 def transact(self,xml):
  with self.connect() as s:
   greeting=self.recv_frame(s);self.send_frame(s,xml);response=self.recv_frame(s);return {'greeting':greeting,'response':response}

def profile_from_env(profile):
 p=profile.upper().replace('.','_')
 return {'host':os.getenv(f'KEDDEH_EPP_{p}_HOST'),'port':int(os.getenv(f'KEDDEH_EPP_{p}_PORT','700')),'cert':os.getenv(f'KEDDEH_EPP_{p}_CLIENT_CERT'),'key':os.getenv(f'KEDDEH_EPP_{p}_CLIENT_KEY'),'ca':os.getenv(f'KEDDEH_EPP_{p}_CA')}

def dispatch(qid,db=None):
 r=Registrar(Path(db)) if db else Registrar()
 try:
  q=r.db.execute('SELECT * FROM registry_queue WHERE id=?',(qid,)).fetchone()
  if not q:raise KeyError('QUEUE_NOT_FOUND')
  gate=r.deployment_gate(q['domain'])
  if not gate['authority_ready']:raise RegistryAuthorityError('REGISTRY_AUTHORITY_NOT_BOUND:'+','.join(gate['missing_authorities']))
  cfg=profile_from_env(r.get_domain(q['domain'])['registry_profile'])
  if not cfg['host']:raise RegistryAuthorityError('EPP_ENDPOINT_NOT_CONFIGURED')
  result=EPPTransport(**cfg).transact(r.epp_xml(qid))
  return {'state':'EPP_RESPONSE_OBSERVED','queue_id':qid,'transport':{'host':cfg['host'],'port':cfg['port']},'response':result}
 finally:r.close()

def main():
 ap=argparse.ArgumentParser();ap.add_argument('queue_id');a=ap.parse_args()
 try:print(json.dumps(dispatch(a.queue_id),indent=2));return 0
 except Exception as e:print(json.dumps({'state':'FAILED_CLOSED','error':type(e).__name__,'detail':str(e)},indent=2));return 2
if __name__=='__main__':raise SystemExit(main())
