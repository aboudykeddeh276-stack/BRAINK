from __future__ import annotations

from pathlib import Path
import socket
import struct

from enterprise.domain_authority_binding import DomainAuthorityBinding


def _query(name: str, qtype: int = 1, txid: int = 0x2970) -> bytes:
    labels = b''.join(bytes([len(x)]) + x.encode() for x in name.rstrip('.').split('.')) + b'\x00'
    return struct.pack('!HHHHHH', txid, 0x0100, 1, 0, 0, 0) + labels + struct.pack('!HH', qtype, 1)


def test_braink_domain_authority_uses_resident_registrar_and_dns(tmp_path: Path) -> None:
    dep = Path('dependencies/SERVERS-KEDDEHSYSTEMS/runtime/domain_authority')
    registrar_path = dep / 'kex_registrar_service.py'
    dns_path = dep / 'kex_dns.py'
    binding = DomainAuthorityBinding(registrar_path, tmp_path / 'authority')

    result = binding.register_domain_authority(
        domain='integration.keddeh',
        ip='127.0.0.1',
        port=8443,
        owner='KEDDEH_SYSTEMS',
        primary_ns='ns1.integration.keddeh',
        admin_rname='hostmaster.integration.keddeh',
        serial=2026090301,
        records=[
            {'name':'integration.keddeh','type':'A','value':'127.0.0.1','ttl':60},
            {'name':'integration.keddeh','type':'NS','value':'ns1.integration.keddeh','ttl':300},
        ],
    )

    assert result['status'] == 'READ_BACK'
    assert result['resolved_ip'] == '127.0.0.1'
    assert result['zone']['zone'] == 'integration.keddeh'
    assert result['records']['A'][0]['value'] == '127.0.0.1'

    dns = binding.load_dns_runtime(dns_path)
    server = dns.KexDNSServer('127.0.0.1', 0)
    response = server._build_response(_query('integration.keddeh', 1))
    txid, flags, qd, an, ns, ar = struct.unpack('!HHHHHH', response[:12])
    assert txid == 0x2970
    assert flags & 0x8000  # QR
    assert flags & 0x0400  # AA
    assert (flags & 0x000F) == 0
    assert qd == 1
    assert an == 1

    nx = server._build_response(_query('missing.integration.keddeh', 1, 0x2971))
    _, nxflags, _, nxan, nxns, _ = struct.unpack('!HHHHHH', nx[:12])
    assert nxflags & 0x0400
    assert (nxflags & 0x000F) == 3
    assert nxan == 0
    assert nxns == 1
