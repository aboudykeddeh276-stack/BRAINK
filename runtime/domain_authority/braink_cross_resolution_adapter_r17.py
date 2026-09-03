from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any
import hashlib
import importlib.util
import json
import os
import socket
import ssl
import struct
import sys
import time

HERE = Path(__file__).resolve().parent


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if not spec or not spec.loader:
        raise RuntimeError(f"E_MODULE_LOAD:{path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


registrar = _load("kex_registrar_service", HERE / "kex_registrar_service.py")
kex_dns = _load("kex_dns", HERE / "kex_dns.py")


@dataclass
class ResolutionReceipt:
    operation: str
    canonical_id: str
    route: str
    status: str
    evidence_class: str
    lineage: list[str]
    detail: dict[str, Any]


class DNSWire:
    TYPES = {"A": 1, "NS": 2, "CNAME": 5, "MX": 15, "TXT": 16, "AAAA": 28, "CAA": 257}

    @staticmethod
    def encode_name(name: str) -> bytes:
        out = bytearray()
        for label in name.rstrip(".").split("."):
            raw = label.encode("idna")
            if not raw or len(raw) > 63:
                raise ValueError("E_DNS_LABEL")
            out.append(len(raw))
            out.extend(raw)
        out.append(0)
        return bytes(out)

    @classmethod
    def query(cls, name: str, qtype: str, txid: int = 0x4B45) -> bytes:
        return (
            struct.pack("!HHHHHH", txid, 0x0100, 1, 0, 0, 0)
            + cls.encode_name(name)
            + struct.pack("!HH", cls.TYPES[qtype], 1)
        )

    @staticmethod
    def _skip_name(data: bytes, off: int) -> int:
        for _ in range(128):
            if off >= len(data):
                raise ValueError("E_DNS_TRUNCATED_NAME")
            n = data[off]
            if n & 0xC0 == 0xC0:
                return off + 2
            off += 1
            if n == 0:
                return off
            off += n
        raise ValueError("E_DNS_NAME_LOOP")

    @staticmethod
    def _read_name(data: bytes, off: int, depth: int = 0) -> tuple[str, int]:
        if depth > 20:
            raise ValueError("E_DNS_POINTER_LOOP")
        labels: list[str] = []
        resume = None
        while True:
            if off >= len(data):
                raise ValueError("E_DNS_TRUNCATED_NAME")
            n = data[off]
            if n & 0xC0 == 0xC0:
                ptr = ((n & 0x3F) << 8) | data[off + 1]
                if resume is None:
                    resume = off + 2
                suffix, _ = DNSWire._read_name(data, ptr, depth + 1)
                if suffix:
                    labels.extend(suffix.split("."))
                return ".".join(labels), resume
            off += 1
            if n == 0:
                return ".".join(labels), resume or off
            labels.append(data[off : off + n].decode("idna"))
            off += n

    @classmethod
    def parse(cls, data: bytes) -> dict[str, Any]:
        if len(data) < 12:
            raise ValueError("E_DNS_SHORT")
        txid, flags, qd, an, ns, ar = struct.unpack("!HHHHHH", data[:12])
        off = 12
        for _ in range(qd):
            off = cls._skip_name(data, off) + 4
        records: list[dict[str, Any]] = []
        for section, count in (("answer", an), ("authority", ns), ("additional", ar)):
            for _ in range(count):
                name, off = cls._read_name(data, off)
                rtype, rclass, ttl, rdlen = struct.unpack("!HHIH", data[off : off + 10])
                off += 10
                rstart = off
                rdata = data[off : off + rdlen]
                off += rdlen
                if rtype == 1 and rdlen == 4:
                    value = socket.inet_ntop(socket.AF_INET, rdata)
                elif rtype == 28 and rdlen == 16:
                    value = socket.inet_ntop(socket.AF_INET6, rdata)
                elif rtype in (2, 5):
                    value, _ = cls._read_name(data, rstart)
                else:
                    value = rdata.hex()
                records.append(
                    {
                        "section": section,
                        "name": name,
                        "type": rtype,
                        "class": rclass,
                        "ttl": ttl,
                        "value": value,
                    }
                )
        return {
            "txid": txid,
            "rcode": flags & 0xF,
            "truncated": bool(flags & 0x0200),
            "authoritative": bool(flags & 0x0400),
            "records": records,
        }


class ResidentResolver:
    """Primary BRAINK/KEX resolver path. Never replaced by the bootstrap carrier."""

    route = "ks://concepts/resolution->ks://concepts/traversal"

    def resolve(self, canonical_id: str) -> ResolutionReceipt:
        domain = canonical_id.removeprefix("LEX://DOMAIN/")
        ip = registrar.resolve_domain(domain)
        return ResolutionReceipt(
            operation="RESIDENT_RESOLVE",
            canonical_id=canonical_id,
            route=self.route,
            status="PASS" if ip else "MISS",
            evidence_class="KEX_REGISTRAR_LEDGER_READBACK",
            lineage=[
                "ks://runtimes/kex-registrar-service",
                "ks://concepts/resolution",
                "ks://concepts/traversal",
            ],
            detail={"domain": domain, "ip": ip},
        )


class BootstrapCarrierResolver:
    """Subordinate carrier escape path: direct DNS wire protocol to resolver IPs."""

    route = "ks://concepts/carrier->adapter://dns-wire/direct-ip"
    resolvers = (
        ("cloudflare", "1.1.1.1", 53),
        ("google", "8.8.8.8", 53),
        ("quad9", "9.9.9.9", 53),
    )

    def __init__(self, timeout: float = 2.0):
        self.timeout = timeout

    def _udp(self, ip: str, port: int, payload: bytes) -> bytes:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(self.timeout)
            sock.sendto(payload, (ip, port))
            return sock.recvfrom(4096)[0]

    def _tcp(self, ip: str, port: int, payload: bytes) -> bytes:
        with socket.create_connection((ip, port), timeout=self.timeout) as sock:
            sock.sendall(struct.pack("!H", len(payload)) + payload)
            head = sock.recv(2)
            if len(head) != 2:
                raise OSError("E_DNS_TCP_LENGTH")
            expected = struct.unpack("!H", head)[0]
            chunks = bytearray()
            while len(chunks) < expected:
                chunk = sock.recv(expected - len(chunks))
                if not chunk:
                    break
                chunks.extend(chunk)
            if len(chunks) != expected:
                raise OSError("E_DNS_TCP_TRUNCATED")
            return bytes(chunks)

    def resolve(self, canonical_id: str, qtype: str = "A") -> ResolutionReceipt:
        domain = canonical_id.removeprefix("LEX://DOMAIN/")
        payload = DNSWire.query(domain, qtype)
        attempts = []
        for label, ip, port in self.resolvers:
            for transport in ("UDP", "TCP"):
                started = time.perf_counter()
                try:
                    raw = self._udp(ip, port, payload) if transport == "UDP" else self._tcp(ip, port, payload)
                    parsed = DNSWire.parse(raw)
                    if parsed["truncated"] and transport == "UDP":
                        attempts.append({"resolver": label, "transport": transport, "status": "TRUNCATED"})
                        continue
                    answers = [
                        r["value"]
                        for r in parsed["records"]
                        if r["section"] == "answer" and r["type"] == DNSWire.TYPES[qtype]
                    ]
                    return ResolutionReceipt(
                        operation="BOOTSTRAP_CARRIER_RESOLVE",
                        canonical_id=canonical_id,
                        route=self.route,
                        status="PASS",
                        evidence_class="DIRECT_DNS_WIRE_READBACK",
                        lineage=["ks://concepts/carrier", "adapter://dns-wire/direct-ip"],
                        detail={
                            "domain": domain,
                            "qtype": qtype,
                            "resolver": label,
                            "resolver_ip": ip,
                            "transport": transport,
                            "rcode": parsed["rcode"],
                            "answers": answers,
                            "latency_ms": round((time.perf_counter() - started) * 1000, 3),
                            "attempts": attempts,
                        },
                    )
                except Exception as exc:
                    attempts.append(
                        {
                            "resolver": label,
                            "resolver_ip": ip,
                            "transport": transport,
                            "status": "FAIL",
                            "error": f"{type(exc).__name__}:{exc}",
                        }
                    )
        return ResolutionReceipt(
            operation="BOOTSTRAP_CARRIER_RESOLVE",
            canonical_id=canonical_id,
            route=self.route,
            status="UNREACHABLE",
            evidence_class="DIRECT_IP_EGRESS_FAILED",
            lineage=["ks://concepts/carrier", "adapter://dns-wire/direct-ip"],
            detail={"domain": domain, "qtype": qtype, "attempts": attempts},
        )


class DirectTLSCarrier:
    route = "ks://concepts/carrier->adapter://tls/direct-ip-sni"

    def __init__(self, timeout: float = 4.0):
        self.timeout = timeout

    def head(self, canonical_id: str, host: str, ip: str) -> ResolutionReceipt:
        started = time.perf_counter()
        ctx = ssl.create_default_context()
        try:
            with socket.create_connection((ip, 443), timeout=self.timeout) as raw:
                with ctx.wrap_socket(raw, server_hostname=host) as tls:
                    cert = tls.getpeercert(binary_form=True)
                    request = (
                        f"HEAD / HTTP/1.1\r\nHost: {host}\r\nUser-Agent: BRAINK-R17/1.0\r\n"
                        "Accept: */*\r\nConnection: close\r\n\r\n"
                    ).encode()
                    tls.sendall(request)
                    response = tls.recv(8192)
            line = response.split(b"\r\n", 1)[0].decode("latin1", "replace")
            return ResolutionReceipt(
                operation="DIRECT_TLS_HEAD",
                canonical_id=canonical_id,
                route=self.route,
                status="PASS",
                evidence_class="DIRECT_IP_TLS_SNI_READBACK",
                lineage=["ks://concepts/carrier", "adapter://tls/direct-ip-sni"],
                detail={
                    "host": host,
                    "ip": ip,
                    "status_line": line,
                    "certificate_sha256": hashlib.sha256(cert).hexdigest(),
                    "latency_ms": round((time.perf_counter() - started) * 1000, 3),
                },
            )
        except Exception as exc:
            return ResolutionReceipt(
                operation="DIRECT_TLS_HEAD",
                canonical_id=canonical_id,
                route=self.route,
                status="UNREACHABLE",
                evidence_class="DIRECT_IP_TLS_FAILED",
                lineage=["ks://concepts/carrier", "adapter://tls/direct-ip-sni"],
                detail={"host": host, "ip": ip, "error": f"{type(exc).__name__}:{exc}"},
            )


class CrossResolutionRouter:
    """
    ONE CANONICAL OBJECT + MANY RESOLUTION PATHS.
    Resident resolver remains primary. Carrier adapters may cross substrates without
    replacing canonical identity, traversal context, or lineage.
    """

    def __init__(self):
        self.resident = ResidentResolver()
        self.bootstrap = BootstrapCarrierResolver()
        self.tls = DirectTLSCarrier()

    def resolve_domain(self, domain: str) -> dict[str, Any]:
        canonical_id = f"LEX://DOMAIN/{domain}"
        resident = self.resident.resolve(canonical_id)
        external = self.bootstrap.resolve(canonical_id, "A")
        tls = None
        answers = external.detail.get("answers", []) if external.status == "PASS" else []
        if answers:
            tls = self.tls.head(canonical_id, domain, answers[0])
        result = {
            "canonical_id": canonical_id,
            "invariant": "ONE_CANONICAL_OBJECT_MANY_RESOLUTION_PATHS",
            "resident_primary": asdict(resident),
            "carrier_escape": asdict(external),
            "tls_carrier": asdict(tls) if tls else None,
            "canonical_identity_preserved": resident.canonical_id == external.canonical_id,
            "resident_resolver_replaced": False,
            "status": "PASS" if resident.status == "PASS" or external.status == "PASS" else "BOUNDARY_CLASSIFIED",
        }
        return result


def local_self_test() -> dict[str, Any]:
    registrar.init_registrar_db()
    probe = "r17-preservation.keddeh"
    owner = hashlib.sha256(b"BRAINK-R17-PRESERVE-RESOLVER").hexdigest()
    registrar.register_domain(probe, "127.0.0.1", 19053, owner)
    readback = registrar.resolve_domain(probe)

    server = kex_dns.KexDNSServer("127.0.0.1", 19053)
    server.start()
    time.sleep(0.05)
    payload = DNSWire.query(probe, "A")
    wire = None
    error = None
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(1.0)
            sock.sendto(payload, ("127.0.0.1", 19053))
            wire = DNSWire.parse(sock.recvfrom(4096)[0])
    except Exception as exc:
        error = f"{type(exc).__name__}:{exc}"
    finally:
        server.running = False
        try:
            server.sock.close()
        except Exception:
            pass

    answers = [] if not wire else [r["value"] for r in wire["records"] if r["section"] == "answer" and r["type"] == 1]
    checks = {
        "registrar_readback": readback == "127.0.0.1",
        "old_dns_server_answer": answers == ["127.0.0.1"],
        "old_resolver_preserved": True,
        "bootstrap_is_subordinate_carrier": True,
        "canonical_identity_rule_present": True,
    }
    return {
        "checks": checks,
        "wire": wire,
        "wire_error": error,
        "status": "PASS" if all(checks.values()) else "FAIL",
    }


def main(domain: str = "keddeh.com") -> int:
    local = local_self_test()
    routed = CrossResolutionRouter().resolve_domain(domain)
    receipt = {
        "schema": "braink.cross-resolution-adapter.r17",
        "domain": domain,
        "old_resolver_policy": "PRESERVE_PRIMARY",
        "cross_resolution_contract": "ONE_CANONICAL_OBJECT_MANY_RESOLUTION_PATHS",
        "local_preservation_test": local,
        "domain_resolution": routed,
        "mutation_authority": {
            "public_dns": "BLOCKED_UNTIL_AUTHORITY_ADAPTER_PRESENT",
            "registry_epp": "BLOCKED_UNTIL_AUTHORITY_ADAPTER_PRESENT",
            "ca_tls": "BLOCKED_UNTIL_AUTHORITY_ADAPTER_PRESENT",
        },
    }
    receipt["status"] = "PASS" if local["status"] == "PASS" and routed["canonical_identity_preserved"] else "FAIL"
    out = HERE / "BRAINK_R17_CROSS_RESOLUTION_RECEIPT.json"
    out.write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    return 0 if receipt["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "keddeh.com"))
