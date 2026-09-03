import socket,ssl,threading,tempfile,subprocess,sys,xml.etree.ElementTree as ET
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'runtime'/'domain_authority'))
from epp_session_adapter_r18 import EPPTransportR18,EPPFrame,EPP_NS

def response(code,msg): return f'<?xml version="1.0"?><epp xmlns="{EPP_NS}"><response><result code="{code}"><msg>{msg}</msg></result></response></epp>'
def greeting(): return f'<?xml version="1.0"?><epp xmlns="{EPP_NS}"><greeting><svID>fixture</svID></greeting></epp>'

def main():
 td=Path(tempfile.mkdtemp())
 (td/'ca.cnf').write_text('[req]\ndistinguished_name=dn\nx509_extensions=v3_ca\nprompt=no\n[dn]\nCN=R18-CA\n[v3_ca]\nbasicConstraints=critical,CA:TRUE\nkeyUsage=critical,keyCertSign,cRLSign\nsubjectKeyIdentifier=hash\nauthorityKeyIdentifier=keyid:always\n')
 subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-keyout',str(td/'ca.key'),'-out',str(td/'ca.crt'),'-days','1','-config',str(td/'ca.cnf')],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 for name,cn in [('server','localhost'),('client','r18-client')]:
  subprocess.run(['openssl','req','-newkey','rsa:2048','-nodes','-keyout',str(td/f'{name}.key'),'-out',str(td/f'{name}.csr'),'-subj',f'/CN={cn}'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  ext=[]
  if name=='server':
   (td/'ext.cnf').write_text('subjectAltName=DNS:localhost\n'); ext=['-extfile',str(td/'ext.cnf')]
  subprocess.run(['openssl','x509','-req','-in',str(td/f'{name}.csr'),'-CA',str(td/'ca.crt'),'-CAkey',str(td/'ca.key'),'-CAcreateserial','-out',str(td/f'{name}.crt'),'-days','1']+ext,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 ctx=ssl.create_default_context(ssl.Purpose.CLIENT_AUTH);ctx.load_cert_chain(td/'server.crt',td/'server.key');ctx.load_verify_locations(td/'ca.crt');ctx.verify_mode=ssl.CERT_REQUIRED
 ls=socket.socket();ls.bind(('127.0.0.1',0));ls.listen(1);port=ls.getsockname()[1]; seen=[]
 def server():
  raw,_=ls.accept();s=ctx.wrap_socket(raw,server_side=True);EPPFrame.send(s,greeting())
  x=EPPFrame.recv(s);seen.append('LOGIN' if ET.fromstring(x).find('.//{'+EPP_NS+'}login') is not None else 'BAD_LOGIN');EPPFrame.send(s,response(1000,'login ok'))
  EPPFrame.recv(s);seen.append('COMMAND');EPPFrame.send(s,response(1000,'command ok'))
  x=EPPFrame.recv(s);seen.append('LOGOUT' if ET.fromstring(x).find('.//{'+EPP_NS+'}logout') is not None else 'BAD_LOGOUT');EPPFrame.send(s,response(1500,'logout ok'));s.close();ls.close()
 threading.Thread(target=server,daemon=True).start()
 cmd=f'<?xml version="1.0"?><epp xmlns="{EPP_NS}"><command><check/></command></epp>'
 r=EPPTransportR18('localhost',port,td/'client.crt',td/'client.key',td/'ca.crt','client-id','secret').transact(cmd)
 assert r.status=='COMPLETED';assert r.sequence==['TLS','GREETING','LOGIN','COMMAND','LOGOUT'];assert seen==['LOGIN','COMMAND','LOGOUT']
 print({'receipt':r.__dict__,'server_seen':seen})

if __name__=='__main__': main()
