import json,os,subprocess,sys,tempfile,time,socket
from pathlib import Path
from dataclasses import asdict
from braink_runtime.report03_mesh import *
ROOT=Path(__file__).parent;PY=sys.executable;SEC='r03-r3';OLD=('A','B','C');NEW=('A','B','D')
def wait(p,timeout=20):
 end=time.time()+timeout
 while time.time()<end:
  if p.exists():
   try:
    d=json.loads(p.read_text());h,pt=d['endpoint'].split(':')
    with socket.create_connection((h,int(pt)),timeout=.2):return d
   except Exception:pass
  time.sleep(.05)
 raise RuntimeError('endpoint timeout '+str(p))
class P:
 def __init__(self,td,n,m=OLD):self.td=Path(td);self.n=n;self.m=m;self.wal=self.td/f'{n}.wal';self.epf=self.td/f'{n}.ep';self.p=None;self.ep=None
 def start(self):
  if self.epf.exists():self.epf.unlink()
  env=os.environ.copy();env['PYTHONPATH']=str(ROOT)
  self.p=subprocess.Popen([PY,str(ROOT/'node_runner.py'),'--node',self.n,'--members',','.join(self.m),'--wal',str(self.wal),'--secret',SEC,'--endpoint-file',str(self.epf)],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True)
  self.ep=wait(self.epf)['endpoint'];return self
 def kill(self):
  if self.p and self.p.poll() is None:self.p.kill();self.p.wait(timeout=5)
 def stop(self):
  self.kill()
def rr(name,status,**kw):return {'scenario':name,'status':status,**kw}
def main():
 out=[]
 with tempfile.TemporaryDirectory() as td:
  ps={n:P(td,n).start() for n in ('A','B','C','D')};eps={n:x.ep for n,x in ps.items()};c=Coordinator(eps,SEC)
  try:
   r,cm=c.propose_commit('A','DIRECTORY_REGISTER',{'coordinate':'L200'});out.append(rr('multiprocess_initial_commit','PASS',index=r.transition.index,committers=cm))
   c.propose_commit('A','DIRECTORY_UPSERT',{'coordinate':'L200','manifestation_id':'M200','endpoint':'tcp://m200','generation':1})
   rec,proof=c.barrier_read('A','L200');out.append(rr('multiprocess_barrier_read','PASS' if rec['manifestations']['M200']['endpoint']=='tcp://m200' else 'FAIL',proof=proof))
   # kill C; A/B quorum continues
   ps['C'].kill();c2=Coordinator({k:v for k,v in eps.items() if k!='C'},SEC);r3,cm3=c2.propose_commit('A','DIRECTORY_UPSERT',{'coordinate':'L200','manifestation_id':'M200','endpoint':'tcp://m201','generation':2});out.append(rr('process_crash_quorum_progress','PASS',index=r3.transition.index,committers=cm3))
   # restart C and catchup
   ps['C'].start();eps['C']=ps['C'].ep;c3=Coordinator(eps,SEC);n=c3.catch_up('A','C');sa=c3.live_states()['A'];sc=c3.live_states()['C'];out.append(rr('process_restart_wal_suffix_catchup','PASS' if sa['root']==sc['root'] else 'FAIL',entries=n,same_root=sa['root']==sc['root']))
   # quorum loss: stop B/C and ensure prepare fails, leaving possible promise but no accepted value
   ps['B'].kill();ps['C'].kill();one=Coordinator({'A':eps['A']},SEC)
   try:one.propose_commit('A','BARRIER',{'q':'loss'});out.append(rr('quorum_loss_fail_closed','FAIL',detail='unexpected commit'))
   except Exception as e:out.append(rr('quorum_loss_fail_closed','PASS',error=f'{type(e).__name__}:{e}'))
   # restart B/C; catch up and prove higher ballot makes progress after orphan promise
   ps['B'].start();ps['C'].start();eps['B']=ps['B'].ep;eps['C']=ps['C'].ep;c4=Coordinator(eps,SEC);c4.catch_up('A','B');c4.catch_up('A','C');rp,cmp=c4.propose_commit('A','BARRIER',{'after_quorum_loss':True});out.append(rr('higher_ballot_after_quorum_loss','PASS',index=rp.transition.index,ballot=rp.transition.ballot,committers=cmp))
   # orphan accept on A only, then coordinator must complete X and place Y next
   st=c4.live_states()['A'];idx=st['index']+1;ballot=st['max_promised']+1;pre={'op':'PREPARE','index':idx,'epoch':st['epoch'],'ballot':ballot,'previous_root':st['root'],'config_hash':st['config_hash']};cl=Client(SEC);pr=cl.call(eps['A'],pre);tx=Transition(idx,st['epoch'],ballot,'A','BARRIER',{'orphan':'X'},st['root'],st['config_hash']);ac=cl.call(eps['A'],{'op':'ACCEPT','transition':asdict(tx)});ry,cmy=c4.propose_commit('A','BARRIER',{'requested':'Y'});out.append(rr('orphan_acceptance_recovery','PASS' if ry.transition.payload=={'requested':'Y'} and ry.transition.index==idx+1 else 'FAIL',requested_index=ry.transition.index,ballot=ry.transition.ballot))
   # joint config ABC -> ABD then progress with C stopped
   bg,bgc=c4.propose_commit('A','BEGIN_RECONFIG',{'new_members':list(NEW)});fn,fnc=c4.propose_commit('A','FINALIZE_RECONFIG',{});joint=len(set(fnc)&set(OLD))>=2 and len(set(fnc)&set(NEW))>=2;out.append(rr('joint_membership_transition','PASS' if joint else 'FAIL',committers=fnc))
   ps['C'].kill();cnew=Coordinator({n:eps[n] for n in NEW},SEC);post,postc=cnew.propose_commit('A','BARRIER',{'new_config':True});out.append(rr('new_config_progress_without_removed_member','PASS' if post.transition.epoch==2 else 'FAIL',epoch=post.transition.epoch,committers=postc))
   bad=Client('wrong').call(eps['A'],{'op':'STATE'});out.append(rr('hmac_auth_negative_control','PASS' if (not bad['ok'] and 'AUTHENTICATION_FAILED' in bad['error']) else 'FAIL',response=bad))
   cap=LinuxBridgeActuator().capability()
   if cap['ready']:out.append(rr('linux_bridge_actuator','AWAITING_NONDESTRUCTIVE_TARGET',capability=cap))
   else:
    try:LinuxBridgeActuator().execute('ENSURE_BRIDGE','kex-r03-br0');out.append(rr('linux_bridge_actuator_fail_closed','FAIL',capability=cap))
    except Exception as e:out.append(rr('linux_bridge_actuator_fail_closed','PASS',capability=cap,error=f'{type(e).__name__}:{e}'))
  finally:
   [x.stop() for x in ps.values()]
 summary={'schema':'kex.report03.multiprocess.r3','scenarios':out,'passed':sum(x['status']=='PASS' for x in out),'awaiting':sum(x['status'].startswith('AWAITING') for x in out),'failed':sum(x['status']=='FAIL' for x in out)}
 print(json.dumps(summary,indent=2));return 0 if summary['failed']==0 else 1
if __name__=='__main__':raise SystemExit(main())