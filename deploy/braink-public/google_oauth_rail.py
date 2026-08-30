#!/usr/bin/env python3
from __future__ import annotations
import base64, hashlib, json, os, secrets, socket, time, urllib.parse, urllib.request
SOCKET=os.environ.get('BRAINK_OAUTH_SOCKET','/tmp/braink-oauth.sock')
SECRET_FILE=os.environ.get('BRAINK_OAUTH_SECRET_FILE','/run/keddeh/secrets/google-oauth.json')
_states={}
def load_cfg():
    with open(SECRET_FILE,'r',encoding='utf-8') as f:return json.load(f)
def b64u(b):return base64.urlsafe_b64encode(b).rstrip(b'=').decode()
def reply(c,obj):c.sendall((json.dumps(obj,separators=(',',':'))+'\n').encode())
def authorize_url(cfg,domain,return_to):
    state=secrets.token_urlsafe(32); verifier=secrets.token_urlsafe(48); challenge=b64u(hashlib.sha256(verifier.encode()).digest())
    redirect=cfg['redirect_uris'][domain]; _states[state]={'verifier':verifier,'domain':domain,'return_to':return_to,'exp':time.time()+600}
    q={'client_id':cfg['client_id'],'redirect_uri':redirect,'response_type':'code','scope':'openid email profile','state':state,'code_challenge':challenge,'code_challenge_method':'S256','access_type':'online','include_granted_scopes':'true'}
    return cfg.get('authorization_endpoint','https://accounts.google.com/o/oauth2/v2/auth')+'?'+urllib.parse.urlencode(q)
def callback(cfg,q):
    st=_states.pop(q.get('state'),None); code=q.get('code')
    if not st or st['exp']<time.time():raise ValueError('STATE_INVALID_OR_EXPIRED')
    if not code:raise ValueError('CODE_MISSING')
    data=urllib.parse.urlencode({'client_id':cfg['client_id'],'client_secret':cfg['client_secret'],'code':code,'code_verifier':st['verifier'],'grant_type':'authorization_code','redirect_uri':cfg['redirect_uris'][st['domain']]}).encode()
    req=urllib.request.Request(cfg.get('token_endpoint','https://oauth2.googleapis.com/token'),data=data,headers={'Content-Type':'application/x-www-form-urlencoded'})
    tok=json.loads(urllib.request.urlopen(req,timeout=15).read()); req=urllib.request.Request(cfg.get('userinfo_endpoint','https://openidconnect.googleapis.com/v1/userinfo'),headers={'Authorization':'Bearer '+tok['access_token']})
    profile=json.loads(urllib.request.urlopen(req,timeout=15).read())
    return {'session':secrets.token_urlsafe(32),'profile':{k:profile.get(k) for k in ('sub','email','name','picture')},'return_to':st['return_to']}
def handle(c):
    line=b''
    while not line.endswith(b'\n'):
        x=c.recv(65536)
        if not x:break
        line+=x
    req=json.loads(line.decode()); cfg=load_cfg(); op=req.get('op')
    if op=='AUTHORIZE_URL':return reply(c,{'status':'PASS','authorization_url':authorize_url(cfg,req['domain'],req.get('return_to','/'))})
    if op=='CALLBACK':return reply(c,{'status':'PASS',**callback(cfg,req['query'])})
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
