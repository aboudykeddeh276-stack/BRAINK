from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Tuple

A_BIT = "1"
B_BIT = "0"
MAX_RUN = 9


@dataclass(frozen=True)
class ABBlock:
    symbol: str
    count: int

    def __post_init__(self) -> None:
        if self.symbol not in ("A", "B"):
            raise ValueError("AB_SYMBOL_INVALID")
        if not (1 <= self.count <= MAX_RUN):
            raise ValueError("AB_COUNT_INVALID")

    @property
    def bit(self) -> str:
        return A_BIT if self.symbol == "A" else B_BIT

    @property
    def token(self) -> str:
        return f"{self.symbol}{self.count}"


def _validate_bits(bits: str) -> None:
    if any(ch not in "01" for ch in bits):
        raise ValueError("AB_BINARY_INPUT_INVALID")


def encode_bits(bits: str) -> List[ABBlock]:
    """Encode a binary string into canonical A1..A9/B1..B9 run blocks.

    A = run of 1s, B = run of 0s.
    Runs longer than 9 are deterministically split into 9-sized blocks.
    """
    _validate_bits(bits)
    if not bits:
        return []

    out: List[ABBlock] = []
    current = bits[0]
    run = 1

    def flush(bit: str, length: int) -> None:
        symbol = "A" if bit == A_BIT else "B"
        while length > MAX_RUN:
            out.append(ABBlock(symbol, MAX_RUN))
            length -= MAX_RUN
        if length:
            out.append(ABBlock(symbol, length))

    for bit in bits[1:]:
        if bit == current:
            run += 1
        else:
            flush(current, run)
            current = bit
            run = 1
    flush(current, run)
    return out


def decode_blocks(blocks: Iterable[ABBlock]) -> str:
    return "".join(block.bit * block.count for block in blocks)


def encode_tokens(bits: str) -> str:
    return "".join(block.token for block in encode_bits(bits))


def parse_tokens(tokens: str) -> List[ABBlock]:
    if len(tokens) % 2:
        raise ValueError("AB_TOKEN_WIDTH_INVALID")
    blocks: List[ABBlock] = []
    for i in range(0, len(tokens), 2):
        symbol, digit = tokens[i], tokens[i + 1]
        if symbol not in "AB" or digit not in "123456789":
            raise ValueError("AB_TOKEN_INVALID")
        blocks.append(ABBlock(symbol, int(digit)))
    return blocks


def canonicalize_tokens(tokens: str) -> str:
    return encode_tokens(decode_blocks(parse_tokens(tokens)))


def pack_18_symbol(blocks: Iterable[ABBlock]) -> Tuple[bytes, int]:
    """Pack each of the 18 AB tokens into a 5-bit code.

    Code 0..8 => A1..A9, 9..17 => B1..B9.
    Returns (bytes, significant_bit_count).
    """
    codes = []
    for block in blocks:
        base = 0 if block.symbol == "A" else 9
        codes.append(base + block.count - 1)

    bit_count = len(codes) * 5
    acc = 0
    nbits = 0
    out = bytearray()
    for code in codes:
        acc = (acc << 5) | code
        nbits += 5
        while nbits >= 8:
            nbits -= 8
            out.append((acc >> nbits) & 0xFF)
            acc &= (1 << nbits) - 1 if nbits else 0
    if nbits:
        out.append((acc << (8 - nbits)) & 0xFF)
    return bytes(out), bit_count


def unpack_18_symbol(payload: bytes, bit_count: int) -> List[ABBlock]:
    if bit_count < 0 or bit_count % 5:
        raise ValueError("AB_PACKED_BIT_COUNT_INVALID")
    total_codes = bit_count // 5
    acc = int.from_bytes(payload, "big")
    padding = len(payload) * 8 - bit_count
    if padding < 0:
        raise ValueError("AB_PACKED_LENGTH_INVALID")
    acc >>= padding
    blocks: List[ABBlock] = []
    for index in range(total_codes):
        shift = (total_codes - index - 1) * 5
        code = (acc >> shift) & 0x1F
        if code > 17:
            raise ValueError("AB_PACKED_CODE_INVALID")
        if code < 9:
            blocks.append(ABBlock("A", code + 1))
        else:
            blocks.append(ABBlock("B", code - 8))
    return blocks


def pack_alternating(blocks: Iterable[ABBlock]) -> Tuple[bytes, int]:
    """Exploit the invariant that run symbols alternate after the first run.

    Wire form: 1 start-state bit followed by one 4-bit count per run.
    Canonical split runs such as A9A3 do not alternate, so adjacent same-state
    chunks are first merged and then re-split logically only at decode output.
    """
    seq = list(blocks)
    if not seq:
        return b"", 0

    # Collapse chunked same-symbol runs into logical runs for this wire form.
    runs: List[Tuple[str, int]] = []
    for block in seq:
        if runs and runs[-1][0] == block.symbol:
            runs[-1] = (block.symbol, runs[-1][1] + block.count)
        else:
            runs.append((block.symbol, block.count))

    # 4-bit counts limit a single wire run to 15, so split >15 while retaining
    # an explicit repeated-state marker would defeat the alternating invariant.
    # This form therefore applies only when logical runs fit 1..15.
    if any(length > 15 for _, length in runs):
        raise ValueError("AB_ALTERNATING_RUN_EXCEEDS_15")

    for i in range(1, len(runs)):
        if runs[i][0] == runs[i - 1][0]:
            raise ValueError("AB_ALTERNATION_INVALID")

    bits = "1" if runs[0][0] == "A" else "0"
    bits += "".join(f"{length:04b}" for _, length in runs)
    bit_count = len(bits)
    padding = (-bit_count) % 8
    raw = int(bits + ("0" * padding), 2).to_bytes((bit_count + padding) // 8, "big")
    return raw, bit_count


def unpack_alternating(payload: bytes, bit_count: int) -> List[ABBlock]:
    if bit_count == 0:
        return []
    if bit_count < 5 or (bit_count - 1) % 4:
        raise ValueError("AB_ALTERNATING_BIT_COUNT_INVALID")
    bits = bin(int.from_bytes(payload, "big"))[2:].zfill(len(payload) * 8)[:bit_count]
    symbol = "A" if bits[0] == "1" else "B"
    blocks: List[ABBlock] = []
    for i in range(1, bit_count, 4):
        count = int(bits[i:i + 4], 2)
        if count < 1:
            raise ValueError("AB_ALTERNATING_ZERO_RUN_INVALID")
        # Restore the canonical 1..9 block contract.
        remaining = count
        while remaining > MAX_RUN:
            blocks.append(ABBlock(symbol, MAX_RUN))
            remaining -= MAX_RUN
        blocks.append(ABBlock(symbol, remaining))
        symbol = "B" if symbol == "A" else "A"
    return blocks


def metrics(bits: str) -> dict:
    blocks = encode_bits(bits)
    token_chars = len(blocks) * 2
    packed18_bits = len(blocks) * 5
    logical_runs = []
    for block in blocks:
        if logical_runs and logical_runs[-1][0] == block.symbol:
            logical_runs[-1] = (block.symbol, logical_runs[-1][1] + block.count)
        else:
            logical_runs.append((block.symbol, block.count))
    alternating_bits = None
    if logical_runs and all(length <= 15 for _, length in logical_runs):
        alternating_bits = 1 + 4 * len(logical_runs)
    elif not logical_runs:
        alternating_bits = 0
    return {
        "raw_bits": len(bits),
        "canonical_blocks": len(blocks),
        "ascii_token_chars": token_chars,
        "packed_18_symbol_bits": packed18_bits,
        "alternating_wire_bits": alternating_bits,
        "logical_runs": len(logical_runs),
    }
