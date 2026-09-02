from __future__ import annotations
from pathlib import Path
import os, signal, sys, tempfile, time

ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))

from modules.kex_wbos.runtime_dispatcher import RuntimeDispatcher
from runtime.reconciler import RuntimeReconciler

with tempfile.TemporaryDirectory(prefix='braink-r27-real-routes-') as td:
    db=Path(td)/'runtime_registry.sqlite3'
    d=RuntimeDispatcher(ROOT,db)
    rec=RuntimeReconciler(d)

    pg=d.register_route('public-gateway','ACTIVE')
    r23=d.register_route('r23-closure','ACTIVE')
    assert pg['observed_state']=='DEFINED' and r23['observed_state']=='DEFINED'

    first=rec.reconcile_once()
    assert any(x['runtime_id']=='runtime://public-gateway' and x['action']=='START' and x['state']=='READY' for x in first)
    assert any(x['runtime_id']=='runtime://r23-closure' and x['action']=='START' and x['state']=='READY' for x in first)

    pg_ready=d.readback('runtime://public-gateway')
    r23_ready=d.readback('runtime://r23-closure')
    assert pg_ready['observed_state']=='READY'
    assert r23_ready['observed_state']=='READY'
    assert pg_ready['last_readback']['ok'] is True
    assert r23_ready['last_readback']['ok'] is True

    # Fault injection: kill the actual public-gateway process group outside the dispatcher.
    old_pid=pg_ready['pid']
    old_generation=pg_ready['generation']
    os.killpg(old_pid,signal.SIGKILL)
    for _ in range(100):
        if not d.processes['runtime://public-gateway'].alive(): break
        time.sleep(.02)
    degraded=d.readback('runtime://public-gateway')
    assert degraded['observed_state']=='STOPPED'

    recovered=rec.reconcile_once()
    assert any(x['runtime_id']=='runtime://public-gateway' and x['action']=='START' and x['state']=='READY' for x in recovered)
    pg_recovered=d.readback('runtime://public-gateway')
    assert pg_recovered['observed_state']=='READY'
    assert pg_recovered['pid'] != old_pid
    assert pg_recovered['generation'] > old_generation
    assert pg_recovered['state_root']
    assert pg_recovered['author_id']=='AKD'

    # Stable reconciliation must read back, not spawn duplicate descendants.
    stable=rec.reconcile_once()
    assert any(x['runtime_id']=='runtime://public-gateway' and x['action']=='READBACK' and x['state']=='READY' for x in stable)
    assert any(x['runtime_id']=='runtime://r23-closure' and x['action']=='READBACK' and x['state']=='READY' for x in stable)

    d.stop('runtime://public-gateway')
    d.stop('runtime://r23-closure')
    assert d.readback('runtime://public-gateway')['observed_state']=='STOPPED'
    assert d.readback('runtime://r23-closure')['observed_state']=='STOPPED'

print('R27_REAL_RUNTIME_ROUTES_PASS')
