# DNS Transport

Covers: `src/braink_runtime/dns_transport.py`.
**Status: LOCALLY_EXECUTED.**

> **Proof boundary.** Authoritative external DNS confirmation is NOT possible
> from sandbox. Status capped at LOCALLY_EXECUTED.
>
> No code path in this module may emit `EXTERNALLY_OBSERVED` or
> `PUBLICLY_DEPLOYED`. `MAX_PROOF_STATUS` is the constant
> `"LOCALLY_EXECUTED"`, every receipt sets `authoritative = False`, and
> `schemas/dns-proof.schema.json` enumerates only
> `NOT_ATTEMPTED`, `LOCAL_EXECUTION_FAILED` and `LOCALLY_EXECUTED`.

---

## Component identity

`braink:dns_transport` version `1.0.0`. Public names: `DNSTransport`,
`DNSRecord`, `DNSProofReceipt`, `build_query`, `parse_response`, `encode_name`,
`RECORD_TYPES`, `RECORD_TYPE_NAMES`, `MAX_PROOF_STATUS`.

## Purpose

Speak DNS directly on the wire — no resolver library, no `getaddrinfo` — so that
the exact bytes sent and received are inspectable, and so that the proof of
"we performed a DNS query" is a byte string rather than a claim.

## Inputs

Domain name; record type (`A`, `AAAA`, `NS`, `CNAME`, `SOA`, `PTR`, `MX`,
`TXT`); resolver address and port; timeout in seconds.

## Outputs

* `list[DNSRecord]` where `DNSRecord = {name, record_type, ttl, value}`.
* `DNSProofReceipt = {query_name, record_type, resolver, authoritative,
  records, timestamp, status}`.
* Instance telemetry: `last_status`, `last_error`, `last_response_meta`.

## Dependencies

Stdlib `socket`, `struct`, `random`, `dataclasses`, `datetime`. No third-party
DNS library, by design.

## Interfaces

```python
txid, wire = build_query("example.com", "A", txid=0x4242)
parsed     = parse_response(wire_response, expected_txid=txid)
t = DNSTransport()
t.query_udp("example.com", "A", resolver="8.8.8.8", port=53, timeout=3.0)
t.query_tcp("example.com", "A", resolver="8.8.8.8", port=53)
t.generate_proof_receipt("example.com", "A", "8.8.8.8")
```

## Reconstruction rules

### Name encoding
`encode_name` strips a trailing dot, splits on `.`, and emits each label as one
length byte followed by its ASCII (or IDNA, for non-ASCII) bytes, terminated by a
zero byte. A label of length 0 or > 63 raises `ValueError`.

### Query construction
Header is `struct.pack("!HHHHHH", txid, 0x0100, 1, 0, 0, 0)`:
transaction id; flags `0x0100` = standard query with recursion desired;
`QDCOUNT=1`; `ANCOUNT=NSCOUNT=ARCOUNT=0`. The question section is the encoded
name followed by `struct.pack("!HH", qtype, 1)` where `1` is class `IN`. When no
`txid` is supplied one is drawn from `random.randint(0, 0xFFFF)`; it is returned
to the caller so the response can be matched.

### Response parsing
Unpack the 12-byte header. Reject data shorter than 12 bytes, and reject a
`txid` mismatch — an unmatched id is a spoofing indicator, not a parse
convenience. Skip each question (name + 4 bytes). For each answer: read the name,
then `struct.unpack("!HHIH", ...)` for type, class, TTL and rdlength, then
`rdlength` bytes of rdata.

**Name decompression** is mandatory: a length byte whose top two bits are set is
a pointer, and the remaining 14 bits are an absolute offset into the message.
Follow it, remembering the first post-pointer offset as the true continuation
point, and abort after 32 hops so a malicious loop cannot hang the parser.

**RDATA decoding**: `A` = four bytes as dotted quad; `AAAA` = eight 16-bit groups
in hex; `TXT` = a concatenation of length-prefixed strings; `NS`/`CNAME`/`PTR` =
a name read from the *message* (so compression works); `MX` = preference plus
name; anything else falls back to hex, which never fails.

The parser returns `{txid, flags, rcode, authoritative_answer_bit, truncated,
questions, answers, counts}`. Note that `authoritative_answer_bit` records what
the packet *claimed*; it is deliberately never copied into the receipt's
`authoritative` field, which is hard-wired to `False`.

### Transport
`query_udp` sends one datagram, reads up to 4096 bytes, parses, and — if the
`TC` bit is set — retries over TCP. `query_tcp` frames the message with a 2-byte
big-endian length prefix and reads exactly that many bytes back. Both catch
`socket.timeout`, `OSError` and `ValueError`, set `last_status =
"LOCAL_EXECUTION_FAILED"`, record `last_error` and **return an empty list**: a
sandbox without egress must degrade to an honest empty result, never to a
fabricated one. Sockets are closed in a `finally` block.

### Receipt
`generate_proof_receipt` performs the query and returns a receipt whose status is
`MAX_PROOF_STATUS` on success and `"LOCAL_EXECUTION_FAILED"` on failure, with
`authoritative = False` in both cases.

## Required skill or skillset

`raw-protocol-transport`, skillset `trust-boundary`.

## Conceptual validation method

Compare the emitted header, question and answer layouts field by field against
RFC 1035 §4.1, including the compression-pointer rule in §4.1.4. Argue that the
status ceiling is structural rather than procedural: the higher statuses are not
merely unused, they are absent from the enum in the schema and unreachable in the
code.

## Practical validation method

`tests/test_dns_transport.py` — 18 tests: label encoding and its guards;
byte-level assertions on the query header (`0x0100`, `QDCOUNT=1`, zeroed
counts) and on the question suffix; parsing of synthetic `A`, `TXT`, multi-answer
and `CNAME` responses built by an in-test response builder and delivered through
a mocked UDP socket; short-data and txid-mismatch rejection; a timeout path that
returns `[]` and `LOCAL_EXECUTION_FAILED`; receipt status capping (asserting the
status is *not* `EXTERNALLY_OBSERVED` or `PUBLICLY_DEPLOYED`); and a live TCP
attempt against TEST-NET-3 (`203.0.113.1`), which must fail gracefully.
`scripts/verify_dns.command` performs a live local execution and prints the wire
bytes.

## Current validation state

**LOCALLY_EXECUTED.** The wire format is unit-proven against synthetic packets;
actual resolution depends on sandbox egress and is never claimed as external
observation.

## Evidence generated

`evidence/DNS_PROOF_RECEIPT.json` — contains the real query wire bytes, the real
transport status and the explicit note
`"Authoritative DNS not confirmed from sandbox — capped at LOCALLY_EXECUTED per
Rule 3"`, together with `"authoritative_external_confirmed": false`.

## Saved representations

`src/braink_runtime/dns_transport.py`, this document,
`schemas/dns-proof.schema.json`, `config/dns_records.json`,
`scripts/verify_dns.command`.

## Remaining limitations or gates

* **The gate.** Raising the status above `LOCALLY_EXECUTED` requires a third
  party, outside this package and outside the sandbox, to observe the published
  record and attest to it. That has not happened and cannot happen here.
* No DNSSEC validation: an answer's authenticity is not verified, only its
  syntax.
* No EDNS0, so responses larger than 512 bytes rely on the TC-bit TCP fallback.
* Only the answer section is decoded; authority and additional sections are
  counted but discarded.
* The 16-bit transaction id and a fixed source port give weak off-path spoofing
  resistance; this is a proof harness, not a hardened resolver.
