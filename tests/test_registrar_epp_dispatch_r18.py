import tempfile,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'runtime'/'domain_authority'))
from registrar_core import Registrar
from registrar_epp_dispatch_r18 import dispatch, RegistryDispatchError

def main():
 td=Path(tempfile.mkdtemp())/'registrar.sqlite3'
 r=Registrar(td)
 qid=r.set_nameservers('keddeh.com',['ns1.keddeh.com','ns2.keddeh.com'])
 q=r.db.execute('SELECT * FROM registry_queue WHERE id=?',(qid,)).fetchone()
 assert q['state']=='AWAITING_REGISTRY_AUTHORITY'
 gate=r.deployment_gate('keddeh.com')
 assert gate['authority_ready'] is False
 r.close()
 try:
  dispatch(qid,str(td)); raise AssertionError('dispatch must fail closed before authority binding')
 except RegistryDispatchError as e:
  assert str(e).startswith('REGISTRY_AUTHORITY_NOT_BOUND:')
 print({'status':'PASS','qid':qid,'authority_gate':gate,'dispatch':'BLOCKED_AS_REQUIRED'})

if __name__=='__main__': main()
