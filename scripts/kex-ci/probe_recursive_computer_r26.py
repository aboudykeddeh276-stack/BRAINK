from __future__ import annotations
import argparse, json, urllib.request

def call(base, method, path, body=None):
    data=None if body is None else json.dumps(body).encode()
    req=urllib.request.Request(base+path,data=data,headers={'Content-Type':'application/json'} if data else {},method=method)
    with urllib.request.urlopen(req,timeout=10) as r:
        return json.load(r)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--base',default='http://127.0.0.1:8811'); a=ap.parse_args()
    health=call(a.base,'GET','/health')
    state=call(a.base,'GET','/state')
    assert health['status']=='PASS' and state['ledger_verified']
    print(json.dumps({'status':'PASS','health':health,'root':state},sort_keys=True))
if __name__=='__main__': main()
