"""Mechanic: Bitcoin address -> output script (scriptPubKey) decoding.

Supports the address types a payout may use on mainnet:
  * P2PKH  (base58check, version 0x00)   -> OP_DUP OP_HASH160 <20> OP_EQUALVERIFY OP_CHECKSIG
  * P2SH   (base58check, version 0x05)   -> OP_HASH160 <20> OP_EQUAL
  * P2WPKH/P2WSH (bech32, HRP "bc", v0)  -> OP_0 <20|32>
  * P2TR   (bech32m, HRP "bc", v1)       -> OP_1 <32>

Reference algorithms: base58check (Satoshi), BIP173 (bech32) and BIP350
(bech32m). This lets the control plane derive a payout script from a configured
address WITHOUT the wallet, so hashing hardware never needs wallet access.
"""

from __future__ import annotations

from .serialize import sha256d

_B58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_BECH32_CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
_BECH32_CONST = 1
_BECH32M_CONST = 0x2BC830A3
_MAINNET_HRP = "bc"


class AddressError(ValueError):
    """Raised when an address is malformed or unsupported."""


# --------------------------------------------------------------------------
# base58check
# --------------------------------------------------------------------------
def _b58decode(value: str) -> bytes:
    num = 0
    for char in value:
        idx = _B58_ALPHABET.find(char)
        if idx == -1:
            raise AddressError(f"invalid base58 character {char!r}")
        num = num * 58 + idx
    full = num.to_bytes((num.bit_length() + 7) // 8, "big") if num else b""
    pad = len(value) - len(value.lstrip("1"))
    return b"\x00" * pad + full


def _b58check_decode(value: str) -> tuple[int, bytes]:
    raw = _b58decode(value)
    if len(raw) < 5:
        raise AddressError("base58check payload too short")
    payload, checksum = raw[:-4], raw[-4:]
    if sha256d(payload)[:4] != checksum:
        raise AddressError("base58check checksum mismatch")
    return payload[0], payload[1:]


# --------------------------------------------------------------------------
# bech32 / bech32m (BIP173 / BIP350)
# --------------------------------------------------------------------------
def _bech32_polymod(values: list[int]) -> int:
    generator = [0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3]
    chk = 1
    for value in values:
        top = chk >> 25
        chk = (chk & 0x1FFFFFF) << 5 ^ value
        for i in range(5):
            chk ^= generator[i] if ((top >> i) & 1) else 0
    return chk


def _bech32_hrp_expand(hrp: str) -> list[int]:
    return [ord(c) >> 5 for c in hrp] + [0] + [ord(c) & 31 for c in hrp]


def _bech32_decode(address: str) -> tuple[str, list[int], int]:
    if address != address.lower() and address != address.upper():
        raise AddressError("bech32 address is mixed case")
    address = address.lower()
    pos = address.rfind("1")
    if pos < 1 or pos + 7 > len(address):
        raise AddressError("bech32 missing/short separator")
    hrp, data_part = address[:pos], address[pos + 1:]
    data: list[int] = []
    for char in data_part:
        idx = _BECH32_CHARSET.find(char)
        if idx == -1:
            raise AddressError(f"invalid bech32 data character {char!r}")
        data.append(idx)
    checksum = _bech32_polymod(_bech32_hrp_expand(hrp) + data)
    return hrp, data[:-6], checksum


def _convertbits(data: list[int], frombits: int, tobits: int, pad: bool) -> list[int]:
    acc = 0
    bits = 0
    ret: list[int] = []
    maxv = (1 << tobits) - 1
    for value in data:
        if value < 0 or (value >> frombits):
            raise AddressError("invalid value in base conversion")
        acc = (acc << frombits) | value
        bits += frombits
        while bits >= tobits:
            bits -= tobits
            ret.append((acc >> bits) & maxv)
    if pad:
        if bits:
            ret.append((acc << (tobits - bits)) & maxv)
    elif bits >= frombits or ((acc << (tobits - bits)) & maxv):
        raise AddressError("invalid padding in base conversion")
    return ret


def _decode_segwit(address: str) -> tuple[int, bytes]:
    hrp, data, checksum = _bech32_decode(address)
    if hrp != _MAINNET_HRP:
        raise AddressError(f"expected mainnet HRP {_MAINNET_HRP!r}, got {hrp!r}")
    if not data:
        raise AddressError("empty witness program")
    witver = data[0]
    if witver > 16:
        raise AddressError("invalid witness version")
    expected = _BECH32_CONST if witver == 0 else _BECH32M_CONST
    if checksum != expected:
        raise AddressError("bech32 checksum invalid for witness version")
    program = bytes(_convertbits(data[1:], 5, 8, False))
    if not 2 <= len(program) <= 40:
        raise AddressError("witness program length out of range")
    if witver == 0 and len(program) not in (20, 32):
        raise AddressError("v0 witness program must be 20 or 32 bytes")
    return witver, program


# --------------------------------------------------------------------------
# public API
# --------------------------------------------------------------------------
def address_to_script(address: str) -> bytes:
    """Decode a mainnet address into its scriptPubKey bytes."""
    if not address:
        raise AddressError("empty address")
    if address.lower().startswith(_MAINNET_HRP + "1"):
        witver, program = _decode_segwit(address)
        opcode = 0x00 if witver == 0 else 0x50 + witver  # OP_0 / OP_1..OP_16
        return bytes([opcode, len(program)]) + program

    version, payload = _b58check_decode(address)
    if version == 0x00:  # P2PKH
        if len(payload) != 20:
            raise AddressError("P2PKH payload must be 20 bytes")
        return b"\x76\xa9\x14" + payload + b"\x88\xac"
    if version == 0x05:  # P2SH
        if len(payload) != 20:
            raise AddressError("P2SH payload must be 20 bytes")
        return b"\xa9\x14" + payload + b"\x87"
    raise AddressError(f"unsupported base58 version byte 0x{version:02x}")
