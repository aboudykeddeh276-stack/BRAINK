"""Minimal DNS transport implemented directly on top of ``socket``.

Proof boundary (Rule 3): everything in this module is capped at
``LOCALLY_EXECUTED``. The sandbox cannot prove that an authoritative
nameserver answered, so no code path may ever emit ``EXTERNALLY_OBSERVED`` or
``PUBLICLY_DEPLOYED``.
"""

from __future__ import annotations

import random
import socket
import struct
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

__all__ = [
    "DNSRecord",
    "DNSProofReceipt",
    "DNSTransport",
    "RECORD_TYPES",
    "RECORD_TYPE_NAMES",
    "build_query",
    "encode_name",
    "parse_response",
    "MAX_PROOF_STATUS",
]

MAX_PROOF_STATUS = "LOCALLY_EXECUTED"

RECORD_TYPES: Dict[str, int] = {
    "A": 1,
    "NS": 2,
    "CNAME": 5,
    "SOA": 6,
    "PTR": 12,
    "MX": 15,
    "TXT": 16,
    "AAAA": 28,
}
RECORD_TYPE_NAMES: Dict[int, str] = {v: k for k, v in RECORD_TYPES.items()}

CLASS_IN = 1


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class DNSRecord:
    name: str
    record_type: str
    ttl: int
    value: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "record_type": self.record_type,
            "ttl": self.ttl,
            "value": self.value,
        }


@dataclass
class DNSProofReceipt:
    query_name: str
    record_type: str
    resolver: str
    authoritative: bool = False
    records: List[Dict[str, Any]] = field(default_factory=list)
    timestamp: str = ""
    status: str = MAX_PROOF_STATUS

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query_name": self.query_name,
            "record_type": self.record_type,
            "resolver": self.resolver,
            "authoritative": self.authoritative,
            "records": list(self.records),
            "timestamp": self.timestamp,
            "status": self.status,
        }


# ---------------------------------------------------------------------------
# Wire format
# ---------------------------------------------------------------------------

def encode_name(name: str) -> bytes:
    """Encode a domain name as a sequence of length-prefixed labels."""
    if name is None or not isinstance(name, str):
        raise ValueError("name must be a string")
    clean = name.strip().rstrip(".")
    if clean == "":
        raise ValueError("name must not be empty")
    out = bytearray()
    for label in clean.split("."):
        encoded = label.encode("idna") if any(ord(c) > 127 for c in label) else label.encode("ascii")
        if len(encoded) == 0 or len(encoded) > 63:
            raise ValueError("invalid DNS label: %r" % label)
        out.append(len(encoded))
        out.extend(encoded)
    out.append(0)
    return bytes(out)


def build_query(name: str, record_type: str = "A", txid: int = None) -> Tuple[int, bytes]:
    """Build a standard recursive DNS query. Returns ``(txid, wire_bytes)``."""
    qtype = RECORD_TYPES.get(str(record_type).upper())
    if qtype is None:
        raise ValueError("unsupported record type: %s" % record_type)
    if txid is None:
        txid = random.randint(0, 0xFFFF)
    header = struct.pack("!HHHHHH", txid, 0x0100, 1, 0, 0, 0)
    question = encode_name(name) + struct.pack("!HH", qtype, CLASS_IN)
    return txid, header + question


def _read_name(data: bytes, offset: int) -> Tuple[str, int]:
    """Read a (possibly compressed) name. Returns ``(name, next_offset)``."""
    labels: List[str] = []
    jumped = False
    next_offset = offset
    hops = 0
    while True:
        if offset >= len(data):
            raise ValueError("truncated DNS name")
        length = data[offset]
        if length == 0:
            offset += 1
            if not jumped:
                next_offset = offset
            break
        if length & 0xC0 == 0xC0:
            if offset + 1 >= len(data):
                raise ValueError("truncated DNS compression pointer")
            pointer = ((length & 0x3F) << 8) | data[offset + 1]
            if not jumped:
                next_offset = offset + 2
            offset = pointer
            jumped = True
            hops += 1
            if hops > 32:
                raise ValueError("DNS compression pointer loop")
            continue
        offset += 1
        labels.append(data[offset:offset + length].decode("ascii", "replace"))
        offset += length
    return ".".join(labels), next_offset


def _decode_rdata(rtype: int, rdata: bytes, data: bytes, rdata_offset: int) -> str:
    if rtype == RECORD_TYPES["A"] and len(rdata) == 4:
        return ".".join(str(b) for b in rdata)
    if rtype == RECORD_TYPES["AAAA"] and len(rdata) == 16:
        return ":".join(
            "%x" % struct.unpack("!H", rdata[i:i + 2])[0] for i in range(0, 16, 2)
        )
    if rtype == RECORD_TYPES["TXT"]:
        parts: List[str] = []
        idx = 0
        while idx < len(rdata):
            length = rdata[idx]
            idx += 1
            parts.append(rdata[idx:idx + length].decode("utf-8", "replace"))
            idx += length
        return "".join(parts)
    if rtype in (RECORD_TYPES["NS"], RECORD_TYPES["CNAME"], RECORD_TYPES["PTR"]):
        name, _ = _read_name(data, rdata_offset)
        return name
    if rtype == RECORD_TYPES["MX"] and len(rdata) >= 3:
        preference = struct.unpack("!H", rdata[:2])[0]
        name, _ = _read_name(data, rdata_offset + 2)
        return "%d %s" % (preference, name)
    return rdata.hex()


def parse_response(data: bytes, expected_txid: int = None) -> Dict[str, Any]:
    """Parse a DNS response message into a structured dict."""
    if data is None or len(data) < 12:
        raise ValueError("DNS response too short")
    txid, flags, qdcount, ancount, nscount, arcount = struct.unpack("!HHHHHH", data[:12])
    if expected_txid is not None and txid != expected_txid:
        raise ValueError("DNS transaction id mismatch")
    offset = 12
    questions: List[str] = []
    for _ in range(qdcount):
        qname, offset = _read_name(data, offset)
        offset += 4
        questions.append(qname)
    records: List[DNSRecord] = []
    for _ in range(ancount):
        rname, offset = _read_name(data, offset)
        if offset + 10 > len(data):
            raise ValueError("truncated DNS answer header")
        rtype, rclass, ttl, rdlength = struct.unpack("!HHIH", data[offset:offset + 10])
        offset += 10
        rdata = data[offset:offset + rdlength]
        value = _decode_rdata(rtype, rdata, data, offset)
        offset += rdlength
        records.append(
            DNSRecord(
                name=rname,
                record_type=RECORD_TYPE_NAMES.get(rtype, str(rtype)),
                ttl=int(ttl),
                value=value,
            )
        )
    return {
        "txid": txid,
        "flags": flags,
        "rcode": flags & 0x000F,
        "authoritative_answer_bit": bool(flags & 0x0400),
        "truncated": bool(flags & 0x0200),
        "questions": questions,
        "answers": records,
        "counts": {
            "qd": qdcount,
            "an": ancount,
            "ns": nscount,
            "ar": arcount,
        },
    }


# ---------------------------------------------------------------------------
# Transport
# ---------------------------------------------------------------------------

class DNSTransport:
    """UDP-first DNS client with TCP fallback and honest status reporting."""

    def __init__(self) -> None:
        self.last_status = "NOT_ATTEMPTED"
        self.last_error = ""
        self.last_response_meta: Dict[str, Any] = {}

    def _record_meta(self, parsed: Dict[str, Any]) -> None:
        self.last_response_meta = {
            "rcode": parsed.get("rcode"),
            "authoritative_answer_bit": parsed.get("authoritative_answer_bit"),
            "truncated": parsed.get("truncated"),
            "counts": parsed.get("counts"),
        }

    def query_udp(
        self,
        name: str,
        record_type: str = "A",
        resolver: str = "8.8.8.8",
        port: int = 53,
        timeout: float = 3.0,
    ) -> List[DNSRecord]:
        txid, wire = build_query(name, record_type)
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(timeout)
            sock.sendto(wire, (resolver, port))
            data, _ = sock.recvfrom(4096)
            parsed = parse_response(data, expected_txid=txid)
            self._record_meta(parsed)
            if parsed["truncated"]:
                self.last_status = "TRUNCATED_RETRY_TCP"
                return self.query_tcp(name, record_type, resolver, port, timeout)
            self.last_status = "LOCALLY_EXECUTED"
            self.last_error = ""
            return parsed["answers"]
        except (socket.timeout, OSError, ValueError) as exc:
            self.last_status = "LOCAL_EXECUTION_FAILED"
            self.last_error = "%s: %s" % (type(exc).__name__, exc)
            return []
        finally:
            if sock is not None:
                sock.close()

    def query_tcp(
        self,
        name: str,
        record_type: str = "A",
        resolver: str = "8.8.8.8",
        port: int = 53,
        timeout: float = 5.0,
    ) -> List[DNSRecord]:
        txid, wire = build_query(name, record_type)
        framed = struct.pack("!H", len(wire)) + wire
        sock = None
        try:
            sock = socket.create_connection((resolver, port), timeout=timeout)
            sock.settimeout(timeout)
            sock.sendall(framed)
            header = self._recv_exact(sock, 2)
            length = struct.unpack("!H", header)[0]
            data = self._recv_exact(sock, length)
            parsed = parse_response(data, expected_txid=txid)
            self._record_meta(parsed)
            self.last_status = "LOCALLY_EXECUTED"
            self.last_error = ""
            return parsed["answers"]
        except (socket.timeout, OSError, ValueError) as exc:
            self.last_status = "LOCAL_EXECUTION_FAILED"
            self.last_error = "%s: %s" % (type(exc).__name__, exc)
            return []
        finally:
            if sock is not None:
                sock.close()

    @staticmethod
    def _recv_exact(sock: socket.socket, count: int) -> bytes:
        chunks = bytearray()
        while len(chunks) < count:
            chunk = sock.recv(count - len(chunks))
            if not chunk:
                raise OSError("connection closed before %d bytes were read" % count)
            chunks.extend(chunk)
        return bytes(chunks)

    def generate_proof_receipt(
        self,
        name: str,
        record_type: str = "A",
        resolver: str = "8.8.8.8",
    ) -> DNSProofReceipt:
        """Query and wrap the outcome in a receipt whose status is capped."""
        records = self.query_udp(name, record_type, resolver)
        status = MAX_PROOF_STATUS
        if self.last_status == "LOCAL_EXECUTION_FAILED":
            status = "LOCAL_EXECUTION_FAILED"
        return DNSProofReceipt(
            query_name=name,
            record_type=str(record_type).upper(),
            resolver=resolver,
            authoritative=False,
            records=[r.to_dict() for r in records],
            timestamp=_utc_now(),
            status=status,
        )
