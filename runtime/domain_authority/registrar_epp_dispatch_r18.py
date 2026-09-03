from __future__ import annotations
import os
from pathlib import Path
from registrar_core import Registrar
from epp_session_adapter_r18 import EPPTransportR18

class RegistryDispatchError(RuntimeError):
    pass

def profile_from_env(profile: str):
    p = profile.upper().replace('.', '_')
    return {
        'host': os.getenv(f'KEDDEH_EPP_{p}_HOST'),
        'port': int(os.getenv(f'KEDDEH_EPP_{p}_PORT', '700')),
        'cert': os.getenv(f'KEDDEH_EPP_{p}_CLIENT_CERT'),
        'key': os.getenv(f'KEDDEH_EPP_{p}_CLIENT_KEY'),
        'ca': os.getenv(f'KEDDEH_EPP_{p}_CA'),
        'client_id': os.getenv(f'KEDDEH_EPP_{p}_CLIENT_ID'),
        'password': os.getenv(f'KEDDEH_EPP_{p}_PASSWORD'),
    }

def dispatch(qid: str, db: str | None = None):
    r = Registrar(Path(db)) if db else Registrar()
    try:
        q = r.db.execute('SELECT * FROM registry_queue WHERE id=?', (qid,)).fetchone()
        if not q:
            raise KeyError('QUEUE_NOT_FOUND')
        gate = r.deployment_gate(q['domain'])
        if not gate['authority_ready']:
            raise RegistryDispatchError('REGISTRY_AUTHORITY_NOT_BOUND:' + ','.join(gate['missing_authorities']))
        profile = r.get_domain(q['domain'])['registry_profile']
        cfg = profile_from_env(profile)
        missing = [k for k in ('host','cert','key','ca','client_id','password') if not cfg.get(k)]
        if missing:
            raise RegistryDispatchError('EPP_SESSION_CONFIGURATION_MISSING:' + ','.join(missing))
        receipt = EPPTransportR18(**cfg).transact(r.epp_xml(qid))
        result = {
            'success': receipt.status == 'COMPLETED',
            'epp_result_code': receipt.result_code,
            'epp_result_message': receipt.result_message,
            'session_sequence': receipt.sequence,
        }
        ack = r.acknowledge_registry(qid, result) if receipt.status in {'COMPLETED','FAILED'} else None
        return {'state': receipt.status, 'queue_id': qid, 'transport': {'host': cfg['host'], 'port': cfg['port']}, 'receipt': receipt.__dict__, 'registry_ack': ack}
    finally:
        r.close()
