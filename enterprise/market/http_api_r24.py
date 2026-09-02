from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlparse
import json
from .service_fabric_r24 import MarketServiceFabric

class ServiceAPI:
    def __init__(self,db_path): self.store=MarketServiceFabric(db_path)
    def handler(self):
        s=self.store
        class H(BaseHTTPRequestHandler):
            def sendj(self,code,obj):
                raw=json.dumps(obj).encode(); self.send_response(code); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(raw))); self.end_headers(); self.wfile.write(raw)
            def body(self):
                n=int(self.headers.get('Content-Length','0')); return json.loads(self.rfile.read(n) or b'{}')
            def do_GET(self):
                if self.path=='/health': return self.sendj(200,{'status':'OK','service':'KEDDEH_SYSTEMS_MARKET_SERVICE_FABRIC_R24'})
                if self.path=='/metrics': return self.sendj(200,s.metrics())
                return self.sendj(404,{'status':'NOT_FOUND'})
            def do_POST(self):
                p=urlparse(self.path).path; b=self.body()
                routes={
                    '/customers': lambda:s.create_customer(b['name'],b.get('email')),
                    '/workspaces': lambda:s.create_workspace(b['customer_id'],b['name']),
                    '/artifacts': lambda:s.write_artifact(b['workspace_id'],b['path'],b['content']),
                    '/sites': lambda:s.create_site(b['customer_id'],b['name'],b['domain'],b.get('site_type','WEBSITE')),
                    '/pages': lambda:s.put_page(b['site_id'],b['slug'],b['title'],b['body']),
                    '/publish/site': lambda:s.publish_site(b['site_id']),
                    '/roles': lambda:s.register_role(b['name'],b['scope'],b.get('supervision_only',False)),
                    '/agents': lambda:s.register_agent(b['name'],b['role_id']),
                    '/work-modules': lambda:s.create_work_module(b['foundry'],b['function'],b['instruction']),
                    '/assignments': lambda:s.assign_agent(b['work_module_id'],b['agent_id'],b['supervisor_id'],b['group_name'],b['scope']),
                    '/server-sets': lambda:s.deploy_server_set(b['business_id'],b['server_family'],b['replicas'],b['config'])
                }
                if p not in routes: return self.sendj(404,{'status':'NOT_FOUND'})
                try: return self.sendj(200,routes[p]())
                except Exception as e: return self.sendj(400,{'status':'ERROR','error':type(e).__name__})
            def log_message(self,*_): pass
        return H
    def serve(self,host='127.0.0.1',port=19620):
        ThreadingHTTPServer((host,port),self.handler()).serve_forever()

if __name__=='__main__':
    ServiceAPI('runtime/market_service_r24.sqlite3').serve()
