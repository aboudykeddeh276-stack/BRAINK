#!/usr/bin/env python3
from __future__ import annotations
import base64, hashlib, hmac, json, os, socket, time, urllib.parse, urllib.request
SOCKET=os.environ.get('BRAINK_STRIPE_SOCKET','/tmp/braink-stripe.sock')
SECRET_FILE=os.environ.get('BRAINK_STRIPE_SECRET_FILE','/run/keddeh/secrets/stripe.json')
def cfg():
    with open(SECRET_FILE,'r',encoding='utf-8') as f:return json.load(f)
def reply(c,obj):c.sendall((json.dumps(obj,separators=(',',':'))+'\n').encode())
def stripe_post(path,fields,secret):
    data=urllib.parse.urlencode(fields,doseq=True).encode(); req=urllib.request.Request('https://api.stripe.com'+path,data=data,headers={'Authorization':'Bearer '+secret,'Content-Type':'application/x-www-form-urlencoded'})
    return json.loads(urllib.request.urlopen(req,timeout=20).read())
def checkout(cg,req):
    domain=req.get('domain','braink.com.au'); product=req.get('product','BRAINK'); price=cg['prices'].get(product) or cg['prices']['BRAINK']
    r=stripe_post('/v1/checkout/sessions',{'mode':'payment','success_url':cg['success_urls'][domain],'cancel_url':cg['cancel_urls'][domain],'line_items[0][price]':price,'line_items[0][quantity]':'1','metadata[domain]':domain,'metadata[product]':product},cg['secret_key'])
    return {'checkout_url':r['url'],'session_id':r['id']}
def verify_webhook(cg,payload,sig_header):
    parts={}
    for p in sig_header.split(','):
        if '=' in p:
            k,v=p.split('=',1);parts.setdefault(k,[]).append(v)
    ts=int(parts.get('t',['0'])[0])
    if abs(int(time.time())-ts)>300:raise ValueError('WEBHOOK_TIMESTAMP_OUT_OF_RANGE')
    expected=hmac.new(cg['webhook_secret'].encode(),f'{ts}.'.encode()+payload,hashlib.sha256).hexdigest()
    if not any(hmac.compare_digest(expected,v) for v in parts.get('v1',[])):raise ValueError('WEBHOOK_SIGNATURE_INVALID')
    return json.loads(payload)
def handle(c):
    line=b''
    while not line.endswith(b'\n'):
        x=c.recv(65536)
        if not x:break
        line+=x
    req=json.loads(line.decode());cg=cfg();op=req.get('op')
    if op=='CREATE_CHECKOUT':return reply(c,{'status':'PASS',**checkout(cg,req['request'])})
    if op=='WEBHOOK':
        ev=verify_webhook(cg,base64.b64decode(req['payload_b64']),req.get('stripe_signature',''));return reply(c,{'status':'PASS','event':{'id':ev.get('id'),'type':ev.get('type')}})
    return reply(c,{'status':'REJECTED','error':'UNKNOWN_OPERATION'})
def main():
    try:os.unlink(SOCKET)
    except FileNotFoundError:pass
    s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);s.bind(SOCKET);os.chmod(SOCKET,0o660);s.listen(32)
    while True:
        c,_=s.accept()
        try:handle(c)
        except Exception as e:reply(c,{'status':'REJECTED','error':type(e).__name__+':'+str(e)})
        finally:c.close()
if __name__=='__main__':main()
