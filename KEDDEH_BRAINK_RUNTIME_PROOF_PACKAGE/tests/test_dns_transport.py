import socket
import struct

import pytest

from braink_runtime import dns_transport
from braink_runtime.dns_transport import (
    MAX_PROOF_STATUS,
    RECORD_TYPES,
    DNSProofReceipt,
    DNSRecord,
    DNSTransport,
    build_query,
    encode_name,
    parse_response,
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def make_response(query: bytes, answers, flags=0x8180):
    """Build a synthetic DNS response for the question inside ``query``."""
    txid = struct.unpack("!H", query[:2])[0]
    question = query[12:]
    body = bytearray()
    for name, rtype, ttl, rdata in answers:
        body += encode_name(name)
        body += struct.pack("!HHIH", rtype, 1, ttl, len(rdata))
        body += rdata
    header = struct.pack("!HHHHHH", txid, flags, 1, len(answers), 0, 0)
    return header + question + bytes(body)


class FakeUDPSocket:
    def __init__(self, *args, **kwargs):
        self.sent = None
        self.closed = False
        self.timeout = None

    def settimeout(self, value):
        self.timeout = value

    def sendto(self, data, addr):
        self.sent = data
        return len(data)

    def recvfrom(self, bufsize):
        return FakeUDPSocket.responder(self.sent), ("8.8.8.8", 53)

    def close(self):
        self.closed = True


class TimeoutUDPSocket(FakeUDPSocket):
    def recvfrom(self, bufsize):
        raise socket.timeout("timed out")


# ---------------------------------------------------------------------------
# wire format
# ---------------------------------------------------------------------------

def test_encode_name_labels():
    assert encode_name("example.com") == b"\x07example\x03com\x00"


def test_encode_name_strips_trailing_dot():
    assert encode_name("example.com.") == encode_name("example.com")


def test_encode_name_rejects_empty():
    with pytest.raises(ValueError):
        encode_name("")
    with pytest.raises(ValueError):
        encode_name(None)


def test_encode_name_rejects_oversized_label():
    with pytest.raises(ValueError):
        encode_name("x" * 64 + ".com")


def test_build_query_header_structure():
    txid, wire = build_query("example.com", "A", txid=0x1234)
    header = struct.unpack("!HHHHHH", wire[:12])
    assert txid == 0x1234
    assert header[0] == 0x1234
    assert header[1] == 0x0100  # standard query, recursion desired
    assert header[2] == 1  # QDCOUNT
    assert header[3:] == (0, 0, 0)  # ANCOUNT, NSCOUNT, ARCOUNT
    assert wire[12:] == encode_name("example.com") + struct.pack("!HH", 1, 1)


def test_build_query_txt_type():
    _, wire = build_query("example.com", "TXT", txid=1)
    qtype = struct.unpack("!H", wire[-4:-2])[0]
    assert qtype == RECORD_TYPES["TXT"]


def test_build_query_random_txid_in_range():
    txid, _ = build_query("example.com")
    assert 0 <= txid <= 0xFFFF


def test_build_query_rejects_unknown_type():
    with pytest.raises(ValueError):
        build_query("example.com", "NOPE")


# ---------------------------------------------------------------------------
# parsing
# ---------------------------------------------------------------------------

def test_parse_response_a_record():
    txid, query = build_query("example.com", "A", txid=0x4242)
    data = make_response(query, [("example.com", RECORD_TYPES["A"], 300, bytes([93, 184, 216, 34]))])
    parsed = parse_response(data, expected_txid=txid)
    assert parsed["rcode"] == 0
    assert parsed["questions"] == ["example.com"]
    assert len(parsed["answers"]) == 1
    record = parsed["answers"][0]
    assert record.record_type == "A"
    assert record.value == "93.184.216.34"
    assert record.ttl == 300


def test_parse_response_txt_record():
    txid, query = build_query("example.com", "TXT", txid=7)
    payload = b"\x0bbraink=true"
    data = make_response(query, [("example.com", RECORD_TYPES["TXT"], 60, payload)])
    parsed = parse_response(data, expected_txid=txid)
    assert parsed["answers"][0].value == "braink=true"
    assert parsed["answers"][0].record_type == "TXT"


def test_parse_response_multiple_answers():
    txid, query = build_query("example.com", "A", txid=9)
    data = make_response(
        query,
        [
            ("example.com", RECORD_TYPES["A"], 30, bytes([1, 2, 3, 4])),
            ("example.com", RECORD_TYPES["A"], 30, bytes([5, 6, 7, 8])),
        ],
    )
    parsed = parse_response(data, expected_txid=txid)
    assert [r.value for r in parsed["answers"]] == ["1.2.3.4", "5.6.7.8"]
    assert parsed["counts"]["an"] == 2


def test_parse_response_cname_uses_name_decoding():
    txid, query = build_query("www.example.com", "A", txid=11)
    rdata = encode_name("example.com")
    data = make_response(query, [("www.example.com", RECORD_TYPES["CNAME"], 60, rdata)])
    parsed = parse_response(data, expected_txid=txid)
    assert parsed["answers"][0].value == "example.com"


def test_parse_response_rejects_short_data():
    with pytest.raises(ValueError):
        parse_response(b"\x00\x01")


def test_parse_response_rejects_txid_mismatch():
    txid, query = build_query("example.com", "A", txid=1)
    data = make_response(query, [])
    with pytest.raises(ValueError):
        parse_response(data, expected_txid=txid + 1)


# ---------------------------------------------------------------------------
# records and transport
# ---------------------------------------------------------------------------

def test_dns_record_construction_and_dict():
    record = DNSRecord(name="braink.test", record_type="A", ttl=120, value="10.0.0.1")
    assert record.to_dict() == {
        "name": "braink.test",
        "record_type": "A",
        "ttl": 120,
        "value": "10.0.0.1",
    }


def test_query_udp_with_mocked_socket(monkeypatch):
    FakeUDPSocket.responder = staticmethod(
        lambda sent: make_response(
            sent, [("example.com", RECORD_TYPES["A"], 300, bytes([93, 184, 216, 34]))]
        )
    )
    monkeypatch.setattr(dns_transport.socket, "socket", FakeUDPSocket)
    transport = DNSTransport()
    records = transport.query_udp("example.com", "A", resolver="203.0.113.1")
    assert len(records) == 1
    assert records[0].value == "93.184.216.34"
    assert transport.last_status == "LOCALLY_EXECUTED"
    assert transport.last_response_meta["rcode"] == 0


def test_query_udp_timeout_returns_empty(monkeypatch):
    monkeypatch.setattr(dns_transport.socket, "socket", TimeoutUDPSocket)
    transport = DNSTransport()
    assert transport.query_udp("example.com", resolver="203.0.113.1", timeout=0.01) == []
    assert transport.last_status == "LOCAL_EXECUTION_FAILED"
    assert "timeout" in transport.last_error.lower()


def test_generate_proof_receipt_status_is_capped(monkeypatch):
    FakeUDPSocket.responder = staticmethod(
        lambda sent: make_response(
            sent, [("braink.test", RECORD_TYPES["A"], 60, bytes([10, 0, 0, 1]))]
        )
    )
    monkeypatch.setattr(dns_transport.socket, "socket", FakeUDPSocket)
    receipt = DNSTransport().generate_proof_receipt("braink.test", "A", "203.0.113.1")
    assert isinstance(receipt, DNSProofReceipt)
    assert receipt.status == "LOCALLY_EXECUTED"
    assert receipt.status not in ("EXTERNALLY_OBSERVED", "PUBLICLY_DEPLOYED")
    assert receipt.authoritative is False
    assert receipt.records[0]["value"] == "10.0.0.1"
    assert receipt.timestamp


def test_generate_proof_receipt_on_failure(monkeypatch):
    monkeypatch.setattr(dns_transport.socket, "socket", TimeoutUDPSocket)
    receipt = DNSTransport().generate_proof_receipt("braink.test", "A", "203.0.113.1")
    assert receipt.status == "LOCAL_EXECUTION_FAILED"
    assert receipt.records == []
    assert receipt.authoritative is False


def test_max_proof_status_constant():
    assert MAX_PROOF_STATUS == "LOCALLY_EXECUTED"


def test_receipt_to_dict_keys():
    receipt = DNSProofReceipt(query_name="a.test", record_type="A", resolver="8.8.8.8")
    assert set(receipt.to_dict()) == {
        "query_name",
        "record_type",
        "resolver",
        "authoritative",
        "records",
        "timestamp",
        "status",
    }


def test_query_tcp_failure_is_graceful():
    transport = DNSTransport()
    # 203.0.113.0/24 is TEST-NET-3, guaranteed non-routable.
    assert transport.query_tcp("example.com", "A", "203.0.113.1", timeout=0.05) == []
    assert transport.last_status == "LOCAL_EXECUTION_FAILED"
