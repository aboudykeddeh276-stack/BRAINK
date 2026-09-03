import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DA = ROOT / 'runtime' / 'domain_authority'
sys.path.insert(0, str(DA))

import kex_registrar_service as legacy
from braink_domain_authority_fabric_r19 import DomainAuthorityFabric


def main():
    td = Path(tempfile.mkdtemp())

    # Isolate the richer registrar database from any prior test state.
    registrar_db = td / 'registrar_v2.sqlite3'

    # Redirect the preserved resolver ledger to test storage without altering its code path.
    legacy.LEDGER_PATH = td / 'legacy' / 'keddeh_registrar.sqlite'
    legacy.init_registrar_db()
    legacy.register_domain('resident-test.keddeh', '127.0.0.44', 8044, 'TEST')

    fabric = DomainAuthorityFabric(registrar_db)

    resident = fabric.resolve('resident-test.keddeh')
    assert resident['status'] == 'PASS'
    assert resident['invariants'] == {
        'one_canonical_object': True,
        'resident_resolver_replaced': False,
        'external_carrier_has_mutation_authority': False,
        'registrar_object_plane_replaces_legacy_ledger': False,
    }
    assert resident['receipts'][0]['status'] == 'PASS'
    assert resident['receipts'][0]['evidence']['ip'] == '127.0.0.44'
    assert len(resident['receipts']) == 2, 'carrier fallback must not run after resident hit'

    mutation = fabric.request_nameserver_change(
        'keddeh.com', ['ns1.keddeh.com', 'ns2.keddeh.com'], execute=True
    )
    assert mutation['status'] == 'PASS'
    assert mutation['dispatch']['state'] == 'BLOCKED'
    assert mutation['queue_receipt']['evidence']['queue']['state'] == 'AWAITING_REGISTRY_AUTHORITY'
    assert mutation['invariants']['canonical_identity_stable'] is True
    assert mutation['invariants']['legacy_resolver_still_present'] is True

    # Prove failed external authority dispatch did not mutate the legacy resolver ledger.
    conn = sqlite3.connect(legacy.LEDGER_PATH)
    try:
        row = conn.execute(
            'SELECT ip_address, port, owner_hash FROM global_routing WHERE domain=?',
            ('resident-test.keddeh',)
        ).fetchone()
    finally:
        conn.close()
    assert row == ('127.0.0.44', 8044, 'TEST')

    print({
        'status': 'PASS',
        'resident_resolution_short_circuit': True,
        'failed_external_mutation_isolated': True,
        'legacy_resolver_preserved': True,
        'canonical_identity_preserved': True,
        'authority_gate_fail_closed': True,
    })


if __name__ == '__main__':
    main()
