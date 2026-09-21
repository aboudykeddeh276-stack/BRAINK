#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,os
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from node_fabric import NodeFabric
HERE=Path(__file__).resolve().parent;DB=Path(os.environ.get('BRAINK_NODE_FABRIC_DB',HERE/'state'/'node_fabric.sqlite3'))
def fabric(): return NodeFabric(DB)
class H(BaseHTTPRequestHandler):
 def log_message(self,fmt,*args): pass
 def j(self,code,obj):
  b=json.dumps(obj,indent=2).encode();self.send_response(code);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
 def do_GET(self):
  p=urlparse(self.path).path
  if p=='/health': return self.j(200,{'ok':fabric().verify()['ok'],'service':'BRAINK_NODE_FABRIC','ledger':fabric().verify()})
  if p=='/graph': return self.j(200,fabric().export_graph())
  if p=='/templates': return self.j(200,{'templates':fabric().export_graph()['templates']})
  if p=='/instances': return self.j(200,{'instances':fabric().export_graph()['instances']})
  return self.j(404,{'error':'not found'})
 def do_POST(self):
  n=int(self.headers.get('Content-Length','0'));body=json.loads(self.rfile.read(n) or b'{}');p=urlparse(self.path).path
  try:
   if p=='/instantiate': return self.j(201,fabric().instantiate(body['template_id'],body.get('version'),body.get('attributes'),body.get('attribution'),body.get('state')))
   if p=='/connect': return self.j(201,fabric().connect(body['source_id'],body['target_id'],body['relation'],body.get('attributes'),body.get('attribution')))
   if p=='/state': return self.j(200,fabric().set_state(body['instance_id'],body['state'],body['observer_id']))
   return self.j(404,{'error':'not found'})
  except Exception as e:return self.j(400,{'error':type(e).__name__+':'+str(e)})
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--host',default='127.0.0.1');ap.add_argument('--port',type=int,default=8791);a=ap.parse_args();print(json.dumps({'service':'BRAINK_NODE_FABRIC','host':a.host,'port':a.port,'db':str(DB)}),flush=True);ThreadingHTTPServer((a.host,a.port),H).serve_forever()
if __name__=='__main__':main()
