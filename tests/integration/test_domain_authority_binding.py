from __future__ import annotations

from pathlib import Path
import socket
import struct
import time

from enterprise.domain_authority_binding import DomainAuthorityBinding


def _query(name: str, qtype: int = 1, txid: int = 0x2970) -> bytes:
    labels = b''.join(bytes([len(x)]) + x.encode() for x in name.rstrip('.').split('.')) + b'\x00'
    return struct.pack('!HHHHHH', txid, 0x0100, 1, 0, 0, 0) + labels + struct.pack('!HH', qtype, 1)


def _free_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]
    finally:
        sock.close()


def _assert_authoritative_a(response: bytes, txid: int) -> None:
    rid, flags, qd, an, ns, ar = struct.unpack('!HHHHHH', response[:12])
    assert rid == txid
    assert flags & 0x8000  # QR
    assert flags & 0x0400  # AA
    assert (flags & 0x000F) == 0
    assert qd == 1
    assert an == 1


def test_braink_domain_authority_uses_resident_registrar_and_dns_udp_tcp(tmp_path: Path) -> None:
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
    port = _free_port()
    server = dns.KexDNSServer('127.0.0.1', port)
    server.start()
    try:
        time.sleep(0.05)

        # UDP wire path: client -> UDP socket -> DNS parser -> registrar -> authoritative response.
        udp_query = _query('integration.keddeh', 1, 0x2970)
        udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp.settimeout(2)
        try:
            udp.sendto(udp_query, ('127.0.0.1', port))
            udp_response, peer = udp.recvfrom(4096)
        finally:
            udp.close()
        assert peer[0] == '127.0.0.1'
        _assert_authoritative_a(udp_response, 0x2970)

        # TCP wire path: length-prefixed DNS message over a real accepted stream socket.
        tcp_query = _query('integration.keddeh', 1, 0x2972)
        with socket.create_connection(('127.0.0.1', port), timeout=2) as tcp:
            tcp.sendall(struct.pack('!H', len(tcp_query)) + tcp_query)
            header = tcp.recv(2)
            assert len(header) == 2
            expected = struct.unpack('!H', header)[0]
            chunks = bytearray()
            while len(chunks) < expected:
                part = tcp.recv(expected - len(chunks))
                assert part
                chunks.extend(part)
        _assert_authoritative_a(bytes(chunks), 0x2972)

        # UDP NXDOMAIN must remain authoritative and carry SOA authority data.
        nx_query = _query('missing.integration.keddeh', 1, 0x2971)
        nx_udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        nx_udp.settimeout(2)
        try:
            nx_udp.sendto(nx_query, ('127.0.0.1', port))
            nx, _ = nx_udp.recvfrom(4096)
        finally:
            nx_udp.close()
        _, nxflags, _, nxan, nxns, _ = struct.unpack('!HHHHHH', nx[:12])
        assert nxflags & 0x0400
        assert (nxflags & 0x000F) == 3
        assert nxan == 0
        assert nxns == 1
    finally:
        server.stop()
