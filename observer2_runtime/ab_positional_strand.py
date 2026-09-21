from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Iterable, Tuple


def _canon(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha(value) -> str:
    return hashlib.sha256(_canon(value)).hexdigest()


@dataclass(frozen=True)
class ABLine:
    """Minimal line-to-line A/B positional proof primitive.

    This is intentionally not a full grammar, authority engine, or execution
    model. It records only the properties currently justified:
    - A(x) and B(x) coexist as a pair on a line;
    - each line has row/position identity;
    - each line can reference the immediately preceding line;
    - line order and position are preserved for linear or row projection.
    """

    line_number: int
    row: int
    position: int
    a_x: int
    b_x: int
    previous_line_hash: str = "0" * 64
    line_hash: str = field(init=False)

    def __post_init__(self) -> None:
        for name, value in (
            ("line_number", self.line_number),
            ("row", self.row),
            ("position", self.position),
            ("a_x", self.a_x),
            ("b_x", self.b_x),
        ):
            if not isinstance(value, int) or value < 1:
                raise ValueError(f"AB_{name.upper()}_INVALID")
        object.__setattr__(self, "line_hash", _sha(self.canonical(include_hash=False)))

    @property
    def token(self) -> str:
        return f"A({self.a_x}) B({self.b_x})"

    def canonical(self, *, include_hash: bool = True) -> dict:
        value = {
            "line_number": self.line_number,
            "row": self.row,
            "position": self.position,
            "A": self.a_x,
            "B": self.b_x,
            "previous_line_hash": self.previous_line_hash,
        }
        if include_hash and hasattr(self, "line_hash"):
            value["line_hash"] = self.line_hash
        return value


@dataclass(frozen=True)
class ABLineStrand:
    strand_id: str
    lines: Tuple[ABLine, ...]
    strand_hash: str = field(init=False)

    def __post_init__(self) -> None:
        if not self.strand_id:
            raise ValueError("AB_STRAND_ID_REQUIRED")
        previous = "0" * 64
        for expected, line in enumerate(self.lines, start=1):
            if line.line_number != expected:
                raise ValueError("AB_LINE_SEQUENCE_INVALID")
            if line.previous_line_hash != previous:
                raise ValueError("AB_LINEAGE_INVALID")
            previous = line.line_hash
        object.__setattr__(
            self,
            "strand_hash",
            _sha({
                "strand_id": self.strand_id,
                "line_hashes": [line.line_hash for line in self.lines],
            }),
        )

    def row(self, row: int) -> Tuple[ABLine, ...]:
        return tuple(sorted(
            (line for line in self.lines if line.row == row),
            key=lambda line: (line.position, line.line_number),
        ))

    def canonical(self) -> dict:
        return {
            "schema": "kex.ab-line-strand-proof.v1",
            "status": "PROOF_OF_POSSIBILITY",
            "strand_id": self.strand_id,
            "strand_hash": self.strand_hash,
            "lines": [line.canonical() for line in self.lines],
        }


def build_line_strand(
    pairs: Iterable[tuple[int, int, int, int]],
    *,
    strand_id: str,
) -> ABLineStrand:
    """Build a proof strand from (row, position, A_x, B_x) tuples."""
    previous = "0" * 64
    lines = []
    for line_number, (row, position, a_x, b_x) in enumerate(pairs, start=1):
        line = ABLine(
            line_number=line_number,
            row=row,
            position=position,
            a_x=a_x,
            b_x=b_x,
            previous_line_hash=previous,
        )
        lines.append(line)
        previous = line.line_hash
    return ABLineStrand(strand_id=strand_id, lines=tuple(lines))


def c_to_z_minus_authority_example(authority: str) -> Tuple[str, ...]:
    """Proof-of-possibility helper only.

    Demonstrates the proposed C..Z minus one authority symbol construction.
    It is NOT part of the canonical A/B line rule and is NOT used automatically.
    """
    domain = tuple(chr(code) for code in range(ord("C"), ord("Z") + 1))
    return tuple(symbol for symbol in domain if symbol != authority)
