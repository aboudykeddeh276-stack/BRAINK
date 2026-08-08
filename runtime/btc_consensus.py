from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass
from typing import Any, Iterable


def dsha256(data: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()


def varint(n: int) -> bytes:
    if n < 0:
        raise ValueError("negative varint")
    if n < 0xFD:
        return bytes([n])
    if n <= 0xFFFF:
        return b"\xfd" + struct.pack("<H", n)
    if n <= 0xFFFFFFFF:
        return b"\xfe" + struct.pack("<I", n)
    if n <= 0xFFFFFFFFFFFFFFFF:
        return b"\xff" + struct.pack("<Q", n)
    raise ValueError("varint overflow")


def script_num(n: int) -> bytes:
    if n == 0:
        return b""
    neg = n < 0
    value = -n if neg else n
    out = bytearray()
    while value:
        out.append(value & 0xFF)
        value >>= 8
    if out[-1] & 0x80:
        out.append(0x80 if neg else 0)
    elif neg:
        out[-1] |= 0x80
    return bytes(out)


def push(data: bytes) -> bytes:
    if len(data) <= 75:
        return bytes([len(data)]) + data
    if len(data) <= 255:
        return b"\x4c" + bytes([len(data)]) + data
    raise ValueError("pushdata too large for coinbase tag")


def bip34_height(height: int) -> bytes:
    return push(script_num(height))


def compact_target(bits: int | str) -> int:
    value = int(bits, 16) if isinstance(bits, str) else bits
    exponent = value >> 24
    mantissa = value & 0x007FFFFF
    if value & 0x00800000 or mantissa == 0:
        raise ValueError("invalid compact target")
    target = mantissa >> (8 * (3 - exponent)) if exponent <= 3 else mantissa << (8 * (exponent - 3))
    if target <= 0 or target >= 1 << 256:
        raise ValueError("compact target out of range")
    return target


BECH32_CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"


def _bech32_polymod(values: Iterable[int]) -> int:
    chk = 1
    gen = (0x3b6a57b2, 0x26508e6d, 0x1ea119fa, 0x3d4233dd, 0x2a1462b3)
    for value in values:
        top = chk >> 25
        chk = ((chk & 0x1ffffff) << 5) ^ value
        for i, g in enumerate(gen):
            if (top >> i) & 1:
                chk ^= g
    return chk


def _hrp_expand(hrp: str) -> list[int]:
    return [ord(x) >> 5 for x in hrp] + [0] + [ord(x) & 31 for x in hrp]


def _convertbits(data: Iterable[int], frombits: int, tobits: int, pad: bool) -> bytes:
    acc = 0
    bits = 0
    out = bytearray()
    maxv = (1 << tobits) - 1
    for value in data:
        if value < 0 or value >> frombits:
            raise ValueError("invalid bech32 data value")
        acc = (acc << frombits) | value
        bits += frombits
        while bits >= tobits:
            bits -= tobits
            out.append((acc >> bits) & maxv)
    if pad:
        if bits:
            out.append((acc << (tobits - bits)) & maxv)
    elif bits >= frombits or ((acc << (tobits - bits)) & maxv):
        raise ValueError("invalid bech32 padding")
    return bytes(out)


def segwit_scriptpubkey(address: str, expected_hrp: str = "bc") -> bytes:
    if not address or address.lower() != address and address.upper() != address:
        raise ValueError("mixed-case bech32 address")
    address = address.lower()
    pos = address.rfind("1")
    if pos < 1 or pos + 7 > len(address):
        raise ValueError("invalid bech32 separator/checksum length")
    hrp, payload = address[:pos], address[pos + 1:]
    if hrp != expected_hrp:
        raise ValueError(f"address HRP {hrp!r} does not match network HRP {expected_hrp!r}")
    try:
        values = [BECH32_CHARSET.index(c) for c in payload]
    except ValueError as exc:
        raise ValueError("invalid bech32 character") from exc
    if _bech32_polymod(_hrp_expand(hrp) + values) != 1:
        raise ValueError("invalid bech32 checksum")
    data = values[:-6]
    if not data:
        raise ValueError("missing witness version")
    version = data[0]
    if version != 0:
        raise ValueError("this runtime currently accepts v0 bech32 payout addresses only")
    program = _convertbits(data[1:], 5, 8, False)
    if len(program) not in (20, 32):
        raise ValueError("invalid v0 witness program length")
    return bytes([version, len(program)]) + program


def merkle_root_internal(hashes: list[bytes]) -> bytes:
    if not hashes:
        raise ValueError("empty merkle tree")
    level = list(hashes)
    while len(level) > 1:
        if len(level) & 1:
            level.append(level[-1])
        level = [dsha256(level[i] + level[i + 1]) for i in range(0, len(level), 2)]
    return level[0]


def display_hash_to_internal(value: str) -> bytes:
    raw = bytes.fromhex(value)
    if len(raw) != 32:
        raise ValueError("hash must be 32 bytes")
    return raw[::-1]


@dataclass(frozen=True)
class Coinbase:
    stripped: bytes
    full: bytes
    txid_internal: bytes
    wtxid_internal: bytes
    witness_commitment: bytes | None


def witness_commitment(template_transactions: list[dict[str, Any]], reserved: bytes) -> bytes:
    if len(reserved) != 32:
        raise ValueError("witness reserved value must be 32 bytes")
    leaves = [b"\x00" * 32]
    for tx in template_transactions:
        leaves.append(display_hash_to_internal(str(tx.get("hash") or tx["txid"])))
    return dsha256(merkle_root_internal(leaves) + reserved)


def build_coinbase(template: dict[str, Any], payout_script: bytes, extranonce: bytes = b"\x00" * 8,
                   tag: bytes = b"/BRAINK-KEX/", witness_reserved: bytes = b"\x00" * 32) -> Coinbase:
    height = int(template["height"])
    value = int(template["coinbasevalue"])
    transactions = list(template.get("transactions") or [])
    script_sig = bip34_height(height) + push(extranonce) + tag
    if not (2 <= len(script_sig) <= 100):
        raise ValueError("coinbase scriptSig must be 2..100 bytes")

    version = struct.pack("<I", 2)
    prevout = b"\x00" * 32 + b"\xff\xff\xff\xff"
    txin = prevout + varint(len(script_sig)) + script_sig + b"\xff\xff\xff\xff"
    outputs = [struct.pack("<Q", value) + varint(len(payout_script)) + payout_script]

    commitment = None
    segwit = bool(transactions) and any((tx.get("hash") and tx.get("hash") != tx.get("txid")) for tx in transactions)
    default_commitment = template.get("default_witness_commitment")
    if segwit or default_commitment:
        if default_commitment:
            commitment_script = bytes.fromhex(str(default_commitment))
            if not commitment_script.startswith(bytes.fromhex("6a24aa21a9ed")):
                raise ValueError("invalid default_witness_commitment script")
            commitment = commitment_script[6:38]
        else:
            commitment = witness_commitment(transactions, witness_reserved)
            commitment_script = bytes.fromhex("6a24aa21a9ed") + commitment
        outputs.append(struct.pack("<Q", 0) + varint(len(commitment_script)) + commitment_script)

    stripped = version + varint(1) + txin + varint(len(outputs)) + b"".join(outputs) + struct.pack("<I", 0)
    if commitment is None:
        full = stripped
    else:
        full = version + b"\x00\x01" + varint(1) + txin + varint(len(outputs)) + b"".join(outputs)
        full += varint(1) + varint(32) + witness_reserved + struct.pack("<I", 0)
    return Coinbase(stripped, full, dsha256(stripped), dsha256(full), commitment)


def transaction_merkle_root(coinbase_txid_internal: bytes, template_transactions: list[dict[str, Any]]) -> bytes:
    leaves = [coinbase_txid_internal]
    leaves.extend(display_hash_to_internal(str(tx["txid"])) for tx in template_transactions)
    return merkle_root_internal(leaves)


def serialize_header(template: dict[str, Any], merkle_internal: bytes, nonce: int, ntime: int | None = None) -> bytes:
    if len(merkle_internal) != 32:
        raise ValueError("merkle root must be 32 bytes")
    version = int(template["version"])
    prev = display_hash_to_internal(str(template["previousblockhash"]))
    timestamp = int(template.get("curtime") if ntime is None else ntime)
    bits = int(str(template["bits"]), 16)
    header = struct.pack("<I", version & 0xFFFFFFFF) + prev + merkle_internal + struct.pack("<III", timestamp, bits, nonce)
    if len(header) != 80:
        raise AssertionError("Bitcoin header serialization must be exactly 80 bytes")
    return header


def assemble_block(header: bytes, coinbase: Coinbase, template_transactions: list[dict[str, Any]]) -> bytes:
    if len(header) != 80:
        raise ValueError("header must be 80 bytes")
    txs = [coinbase.full]
    for tx in template_transactions:
        raw = bytes.fromhex(str(tx["data"]))
        if not raw:
            raise ValueError("template transaction data is empty")
        txs.append(raw)
    return header + varint(len(txs)) + b"".join(txs)


def build_candidate(template: dict[str, Any], payout_address: str, extranonce: bytes, nonce: int,
                    ntime: int | None = None, network_hrp: str = "bc") -> dict[str, Any]:
    payout = segwit_scriptpubkey(payout_address, network_hrp)
    transactions = list(template.get("transactions") or [])
    coinbase = build_coinbase(template, payout, extranonce)
    merkle = transaction_merkle_root(coinbase.txid_internal, transactions)
    header = serialize_header(template, merkle, nonce, ntime)
    digest = dsha256(header)
    target = compact_target(str(template["bits"]))
    block = assemble_block(header, coinbase, transactions)
    return {
        "block_hex": block.hex(),
        "header_hex": header.hex(),
        "block_hash": digest[::-1].hex(),
        "hash_integer": int.from_bytes(digest, "little"),
        "target": target,
        "target_valid": int.from_bytes(digest, "little") <= target,
        "merkle_root": merkle[::-1].hex(),
        "coinbase_txid": coinbase.txid_internal[::-1].hex(),
        "coinbase_hex": coinbase.full.hex(),
        "witness_commitment": coinbase.witness_commitment.hex() if coinbase.witness_commitment else None,
        "nonce": nonce,
        "ntime": int(template.get("curtime") if ntime is None else ntime),
        "extranonce": extranonce.hex(),
        "workid": template.get("workid"),
    }
