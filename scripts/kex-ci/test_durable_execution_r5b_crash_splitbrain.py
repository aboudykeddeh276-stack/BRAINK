from pathlib import Path
import concurrent.futures, json, os, sqlite3, subprocess, sys, tempfile, time
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from enterprise.orchestration.durable_execution_r5 import SignedEnvelopeAuthority, DomainAuthorityAtomicCoordinator, StaleEpochError

base=Path(tempfile.mkdtemp(prefix='keddah-r5b-')); control=base/'control.sqlite3'; authority=base/'authority.sqlite3'; DomainAuthorityAtomicCoordinator(control,authority)
child=base/'crash_child.py'
child.write_text(f'''import sqlite3,os,time\ncontrol={str(control)!r}; auth={str(authority)!r}\ndb=sqlite3.connect(control,isolation_level=None);db.execute("PRAGMA journal_mode=DELETE");db.execute("ATTACH DATABASE ? AS authority",(auth,));db.execute("BEGIN IMMEDIATE")\ndb.execute("INSERT INTO tx_journal VALUES(?,?,?,?,NULL)",(\"tx-hard-crash\",\"hard-crash.keddeh\",\"STARTED\",time.time_ns()))\ndb.execute("INSERT INTO domains VALUES(?,?,?,?,?,NULL)",(\"DOM-HARD\",\"hard-crash.keddeh\",\"KEDDEH_INTERNAL\",\"BOUND_AUTHORITATIVE\",\"KEDDEH_SYSTEMS\"))\ndb.execute("INSERT INTO authority.zones VALUES(?,?,?,?,?,?)",(\"hard-crash.keddeh\",\"ns1.hard-crash.keddeh\",\"hostmaster.hard-crash.keddeh\",2026090301,\"KEDDEH_SYSTEMS\",\"ACTIVE\"))\ndb.execute("INSERT INTO authority.zone_records VALUES(?,?,?,?,?,?)",(\"hard-crash.keddeh\",\"hard-crash.keddeh\",\"A\",\"127.0.0.1\",300,\"ACTIVE\"))\nos._exit(137)\n''')
p=subprocess.run([sys.executable,str(child)]); coord=DomainAuthorityAtomicCoordinator(control,authority); obs=coord.observe('hard-crash.keddeh'); c=sqlite3.connect(control); j=c.execute("SELECT * FROM tx_journal WHERE tx_id='tx-hard-crash'").fetchone(); c.close(); hard_crash_ok=(p.returncode==137 and obs['control'] is None and obs['zone'] is None and not obs['records'] and j is None)
ledger=base/'leases.sqlite3'; key=b'K'*32; a=SignedEnvelopeAuthority(ledger,key); a.acquire_lease('WORK-SPLIT','seed')
def contender(i):
    x=SignedEnvelopeAuthority(ledger,key)
    try: return {'i':i,'won':True,'epoch':x.acquire_lease('WORK-SPLIT',f'agent-{i}',requested_epoch=2)}
    except StaleEpochError: return {'i':i,'won':False,'stale':True}
with concurrent.futures.ThreadPoolExecutor(max_workers=20) as ex: results=list(ex.map(contender,range(20)))
wins=[x for x in results if x.get('won')]; current=a.current_lease('WORK-SPLIT'); split_ok=(len(wins)==1 and current[0]==2 and current[1]==f"agent-{wins[0]['i']}")
report={'schema':'keddah.durable-execution.hard-crash-splitbrain.r5b/v1','hard_process_crash':{'returncode':p.returncode,'observation':obs,'journal_row':j,'rollback_verified':hard_crash_ok},'split_brain_lease_race':{'contenders':20,'winners':wins,'winner_count':len(wins),'current_lease':current,'fenced':split_ok},'all_passed':hard_crash_ok and split_ok}; print(json.dumps(report,indent=2))
