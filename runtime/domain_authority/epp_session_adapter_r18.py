from __future__ import annotations
import socket, ssl, struct, xml.etree.ElementTree as ET
from dataclasses import dataclass

EPP_NS='urn:ietf:params:xml:ns:epp-1.0'
OBJ_URIS=['urn:ietf:params:xml:ns:domain-1.0','urn:ietf:params:xml:ns:host-1.0','urn:ietf:params:xml:ns:contact-1.0']
EXT_URIS=['urn:ietf:params:xml:ns:secDNS-1.1']

class EPPError(RuntimeError): pass
class EPPAuthorityError(EPPError): pass

@dataclass
class EPPReceipt:
    status:str
    sequence:list[str]
    result_code:int|None
    result_message:str|None
    command_response:str|None

class EPPFrame:
    MAX=8*1024*1024
    @staticmethod
    def send(sock,xml:str):
        b=xml.encode('utf-8'); sock.sendall(struct.pack('!I',len(b)+4)+b)
    @classmethod
    def recv(cls,sock):
        hdr=b''
        while len(hdr)<4:
            c=sock.recv(4-len(hdr))
            if not c: raise ConnectionError('EPP_EOF')
            hdr+=c
        n=struct.unpack('!I',hdr)[0]
        if n<5 or n>cls.MAX: raise ValueError('INVALID_EPP_FRAME_LENGTH')
        data=b''
        while len(data)<n-4:
            c=sock.recv(n-4-len(data))
            if not c: raise ConnectionError('EPP_EOF')
            data+=c
        return data.decode('utf-8','replace')

def _xml_text(parent, tag, text):
    x=ET.SubElement(parent,f'{{{EPP_NS}}}{tag}'); x.text=text; return x

def login_xml(client_id,password,obj_uris=OBJ_URIS,ext_uris=EXT_URIS):
    if not client_id or not password: raise EPPAuthorityError('EPP_LOGIN_CREDENTIALS_REQUIRED')
    root=ET.Element(f'{{{EPP_NS}}}epp'); cmd=ET.SubElement(root,f'{{{EPP_NS}}}command'); login=ET.SubElement(cmd,f'{{{EPP_NS}}}login')
    _xml_text(login,'clID',client_id); _xml_text(login,'pw',password)
    opts=ET.SubElement(login,f'{{{EPP_NS}}}options'); _xml_text(opts,'version','1.0'); _xml_text(opts,'lang','en')
    svcs=ET.SubElement(login,f'{{{EPP_NS}}}svcs')
    for uri in obj_uris: _xml_text(svcs,'objURI',uri)
    if ext_uris:
        ext=ET.SubElement(svcs,f'{{{EPP_NS}}}svcExtension')
        for uri in ext_uris: _xml_text(ext,'extURI',uri)
    return ET.tostring(root,encoding='unicode',xml_declaration=True)

def logout_xml():
    root=ET.Element(f'{{{EPP_NS}}}epp'); cmd=ET.SubElement(root,f'{{{EPP_NS}}}command'); ET.SubElement(cmd,f'{{{EPP_NS}}}logout')
    return ET.tostring(root,encoding='unicode',xml_declaration=True)

def result_code(xml):
    root=ET.fromstring(xml); r=root.find('.//{urn:ietf:params:xml:ns:epp-1.0}result')
    if r is None: return None,None
    msg=r.find('{urn:ietf:params:xml:ns:epp-1.0}msg')
    return int(r.attrib.get('code','0')), (msg.text if msg is not None else None)

class EPPTransportR18:
    def __init__(self,host,port=700,cert=None,key=None,ca=None,client_id=None,password=None,timeout=10):
        self.host=host; self.port=int(port); self.cert=cert; self.key=key; self.ca=ca; self.client_id=client_id; self.password=password; self.timeout=timeout
    def _context(self):
        if not self.cert or not self.key or not self.ca: raise EPPAuthorityError('MUTUAL_TLS_MATERIAL_REQUIRED')
        ctx=ssl.create_default_context(ssl.Purpose.SERVER_AUTH,cafile=self.ca)
        ctx.load_cert_chain(self.cert,self.key); ctx.minimum_version=ssl.TLSVersion.TLSv1_2; ctx.check_hostname=True
        return ctx
    def connect(self):
        raw=socket.create_connection((self.host,self.port),self.timeout)
        return self._context().wrap_socket(raw,server_hostname=self.host)
    def transact(self,command_xml):
        seq=[]
        with self.connect() as s:
            EPPFrame.recv(s); seq.append('TLS'); seq.append('GREETING')
            EPPFrame.send(s,login_xml(self.client_id,self.password)); login_resp=EPPFrame.recv(s); seq.append('LOGIN')
            lc,lm=result_code(login_resp)
            if lc is None or lc>=2000: raise EPPAuthorityError(f'EPP_LOGIN_FAILED:{lc}:{lm}')
            EPPFrame.send(s,command_xml); command_resp=EPPFrame.recv(s); seq.append('COMMAND')
            cc,cm=result_code(command_resp)
            EPPFrame.send(s,logout_xml()); EPPFrame.recv(s); seq.append('LOGOUT')
            status='COMPLETED' if cc==1000 else ('PENDING' if cc==1001 else 'FAILED')
            return EPPReceipt(status,seq,cc,cm,command_resp)
