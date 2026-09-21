from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Iterable, Sequence, Tuple

DOMAIN_C_TO_Z: Tuple[str, ...] = tuple(chr(code) for code in range(ord("C"), ord("Z") + 1))
BODMAS_AUTHORITY_CHAIN: Tuple[str, ...] = ("B", "O", "D", "M", "A", "S")


def _canon(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha(value) -> str:
    return hashlib.sha256(_canon(value)).hexdigest()


def _select(domain: Sequence[str], x: int) -> str:
    if not domain:
        raise ValueError("AB_POSITIONAL_DOMAIN_EMPTY")
    if not isinstance(x, int) or x < 1:
        raise ValueError("AB_POSITION_X_INVALID")
    return domain[(x - 1) % len(domain)]


@dataclass(frozen=True)
class ABAuthorityPolicy:
    """Authority-controlled positional symbol policy.

    The base positional domain is C..Z. A selects from the full domain.
    B selects from the same domain after excluding the authority symbol
    resolved for the current line. Authority semantics are data, not hidden
    control flow, so the chain can be replaced without changing strand identity.
    """

    chain: Tuple[str, ...] = BODMAS_AUTHORITY_CHAIN
    base_domain: Tuple[str, ...] = DOMAIN_C_TO_Z

    def __post_init__(self) -> None:
        if not self.chain:
            raise ValueError("AB_AUTHORITY_CHAIN_EMPTY")
        if len(set(self.base_domain)) != len(self.base_domain):
            raise ValueError("AB_BASE_DOMAIN_DUPLICATE")
        if any(len(symbol) != 1 for symbol in self.base_domain):
            raise ValueError("AB_BASE_DOMAIN_SYMBOL_INVALID")

    def authority_for_line(self, line_number: int) -> str:
        if not isinstance(line_number, int) or line_number < 1:
            raise ValueError("AB_LINE_NUMBER_INVALID")
        return self.chain[(line_number - 1) % len(self.chain)]

    def a_domain(self, line_number: int) -> Tuple[str, ...]:
        _ = self.authority_for_line(line_number)
        return self.base_domain

    def b_domain(self, line_number: int) -> Tuple[str, ...]:
        authority = self.authority_for_line(line_number)
        return tuple(symbol for symbol in self.base_domain if symbol != authority)


@dataclass(frozen=True)
class ABPosition:
    line_number: int
    row: int
    position: int
    x: int

    def __post_init__(self) -> None:
        for name, value in (
            ("line_number", self.line_number),
            ("row", self.row),
            ("position", self.position),
            ("x", self.x),
        ):
            if not isinstance(value, int) or value < 1:
                raise ValueError(f"AB_{name.upper()}_INVALID")

    def canonical(self) -> dict:
        return {
            "line_number": self.line_number,
            "row": self.row,
            "position": self.position,
            "x": self.x,
        }


@dataclass(frozen=True)
class ABPair:
    position: ABPosition
    a_symbol: str
    b_symbol: str
    authority_symbol: str
    authority_chain: Tuple[str, ...]
    previous_line_hash: str
    dynamic: str = "POSITIONAL_STRAND"
    line_hash: str = field(init=False)

    def __post_init__(self) -> None:
        if self.a_symbol not in DOMAIN_C_TO_Z:
            raise ValueError("AB_A_SYMBOL_OUT_OF_DOMAIN")
        if self.b_symbol not in DOMAIN_C_TO_Z:
            raise ValueError("AB_B_SYMBOL_OUT_OF_DOMAIN")
        if self.b_symbol == self.authority_symbol:
            raise ValueError("AB_B_AUTHORITY_EXCLUSION_VIOLATION")
        body = self.canonical(include_hash=False)
        object.__setattr__(self, "line_hash", _sha(body))

    @property
    def token(self) -> str:
        return f"A({self.a_symbol}{self.position.x})B({self.b_symbol}{self.position.x})"

    def canonical(self, *, include_hash: bool = True) -> dict:
        out = {
            "dynamic": self.dynamic,
            "position": self.position.canonical(),
            "a_symbol": self.a_symbol,
            "b_symbol": self.b_symbol,
            "authority_symbol": self.authority_symbol,
            "authority_chain": list(self.authority_chain),
            "previous_line_hash": self.previous_line_hash,
        }
        if include_hash and hasattr(self, "line_hash"):
            out["line_hash"] = self.line_hash
        return out


@dataclass(frozen=True)
class ABStrand:
    strand_id: str
    lines: Tuple[ABPair, ...]
    strand_hash: str = field(init=False)

    def __post_init__(self) -> None:
        if not self.strand_id:
            raise ValueError("AB_STRAND_ID_REQUIRED")
        previous = "0" * 64
        for expected_line, pair in enumerate(self.lines, start=1):
            if pair.position.line_number != expected_line:
                raise ValueError("AB_STRAND_LINE_SEQUENCE_INVALID")
            if pair.previous_line_hash != previous:
                raise ValueError("AB_STRAND_LINEAGE_INVALID")
            previous = pair.line_hash
        object.__setattr__(
            self,
            "strand_hash",
            _sha({
                "strand_id": self.strand_id,
                "line_hashes": [line.line_hash for line in self.lines],
            }),
        )

    def row(self, row: int) -> Tuple[ABPair, ...]:
        return tuple(line for line in self.lines if line.position.row == row)

    def line(self, line_number: int) -> ABPair:
        return self.lines[line_number - 1]

    def canonical(self) -> dict:
        return {
            "schema": "kex.ab-positional-strand.v1",
            "strand_id": self.strand_id,
            "strand_hash": self.strand_hash,
            "lines": [line.canonical() for line in self.lines],
        }


def build_pair(
    *,
    line_number: int,
    row: int,
    position: int,
    x: int,
    previous_line_hash: str = "0" * 64,
    policy: ABAuthorityPolicy | None = None,
) -> ABPair:
    policy = policy or ABAuthorityPolicy()
    authority = policy.authority_for_line(line_number)
    a_symbol = _select(policy.a_domain(line_number), x)
    b_symbol = _select(policy.b_domain(line_number), x)
    return ABPair(
        position=ABPosition(line_number=line_number, row=row, position=position, x=x),
        a_symbol=a_symbol,
        b_symbol=b_symbol,
        authority_symbol=authority,
        authority_chain=policy.chain,
        previous_line_hash=previous_line_hash,
    )


def build_strand(
    positions: Iterable[tuple[int, int, int]],
    *,
    strand_id: str,
    policy: ABAuthorityPolicy | None = None,
) -> ABStrand:
    """Build a linear strand from (row, position, x) tuples."""
    policy = policy or ABAuthorityPolicy()
    previous = "0" * 64
    lines = []
    for line_number, (row, position, x) in enumerate(positions, start=1):
        pair = build_pair(
            line_number=line_number,
            row=row,
            position=position,
            x=x,
            previous_line_hash=previous,
            policy=policy,
        )
        lines.append(pair)
        previous = pair.line_hash
    return ABStrand(strand_id=strand_id, lines=tuple(lines))


def matrix_projection(strand: ABStrand) -> dict[int, list[dict]]:
    rows: dict[int, list[dict]] = {}
    for line in strand.lines:
        rows.setdefault(line.position.row, []).append({
            "line_number": line.position.line_number,
            "position": line.position.position,
            "x": line.position.x,
            "A": line.a_symbol,
            "B": line.b_symbol,
            "authority": line.authority_symbol,
            "line_hash": line.line_hash,
        })
    for values in rows.values():
        values.sort(key=lambda item: (item["position"], item["line_number"]))
    return rows


def dna_projection(strand: ABStrand) -> list[dict]:
    """Linear projection preserving pair order, position and lineage."""
    return [
        {
            "index": line.position.line_number,
            "pair": [line.a_symbol, line.b_symbol],
            "x": line.position.x,
            "row": line.position.row,
            "position": line.position.position,
            "authority": line.authority_symbol,
            "previous": line.previous_line_hash,
            "hash": line.line_hash,
        }
        for line in strand.lines
    ]
