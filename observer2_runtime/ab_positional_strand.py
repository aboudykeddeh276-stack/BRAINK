from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Iterable, Tuple

DOMAIN_C_TO_Z: Tuple[str, ...] = tuple(chr(code) for code in range(ord("C"), ord("Z") + 1))
BODMAS_AUTHORITY_CHAIN: Tuple[str, ...] = ("B", "O", "D", "M", "A", "S")


def _canon(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha(value) -> str:
    return hashlib.sha256(_canon(value)).hexdigest()


def _select(domain: Tuple[str, ...], x: int) -> str:
    if not isinstance(x, int) or x < 1:
        raise ValueError("AB_X_INVALID")
    if not domain:
        raise ValueError("AB_DOMAIN_EMPTY")
    return domain[(x - 1) % len(domain)]


@dataclass(frozen=True)
class ABAuthorityRule:
    """Valid A/B positional rule definition.

    A(x): select x from C..Z.
    B(x): select x from C..Z after excluding the explicitly supplied
          authority symbol when that symbol is present in C..Z.

    BODMAS is retained as the defined authority chain. The runtime does not
    invent which member governs a line. The governing authority is an explicit
    input to a line transition.
    """

    domain: Tuple[str, ...] = DOMAIN_C_TO_Z
    authority_chain: Tuple[str, ...] = BODMAS_AUTHORITY_CHAIN

    def __post_init__(self) -> None:
        if not self.domain:
            raise ValueError("AB_DOMAIN_EMPTY")
        if not self.authority_chain:
            raise ValueError("AB_AUTHORITY_CHAIN_EMPTY")

    def a_domain(self) -> Tuple[str, ...]:
        return self.domain

    def b_domain(self, authority_symbol: str) -> Tuple[str, ...]:
        if authority_symbol not in self.authority_chain:
            raise ValueError("AB_AUTHORITY_NOT_IN_CHAIN")
        return tuple(symbol for symbol in self.domain if symbol != authority_symbol)

    def resolve(self, *, x: int, authority_symbol: str) -> tuple[str, str]:
        return (
            _select(self.a_domain(), x),
            _select(self.b_domain(authority_symbol), x),
        )

    def possibilities(self, *, x: int) -> Tuple[dict, ...]:
        """Enumerate valid authority-derived outcomes for one line.

        This is proof of the rule's possibilities. It does not choose or execute
        one authority branch as globally authoritative.
        """
        out = []
        for authority in self.authority_chain:
            a_symbol, b_symbol = self.resolve(x=x, authority_symbol=authority)
            out.append({
                "authority": authority,
                "x": x,
                "A": a_symbol,
                "B": b_symbol,
            })
        return tuple(out)


@dataclass(frozen=True)
class ABLine:
    line_number: int
    row: int
    position: int
    x: int
    authority_symbol: str
    a_symbol: str
    b_symbol: str
    previous_line_hash: str = "0" * 64
    line_hash: str = field(init=False)

    def __post_init__(self) -> None:
        for name, value in (
            ("line_number", self.line_number),
            ("row", self.row),
            ("position", self.position),
            ("x", self.x),
        ):
            if not isinstance(value, int) or value < 1:
                raise ValueError(f"AB_{name.upper()}_INVALID")
        object.__setattr__(self, "line_hash", _sha(self.canonical(include_hash=False)))

    @property
    def token(self) -> str:
        return f"A({self.a_symbol}:{self.x}) B({self.b_symbol}:{self.x})"

    def canonical(self, *, include_hash: bool = True) -> dict:
        out = {
            "line_number": self.line_number,
            "row": self.row,
            "position": self.position,
            "x": self.x,
            "authority_symbol": self.authority_symbol,
            "A": self.a_symbol,
            "B": self.b_symbol,
            "previous_line_hash": self.previous_line_hash,
        }
        if include_hash and hasattr(self, "line_hash"):
            out["line_hash"] = self.line_hash
        return out


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
            "schema": "kex.ab-line-strand-rule.v1",
            "rule_status": "VALID_RULE",
            "execution_status": "EXPLICIT_AUTHORITY_PER_LINE",
            "strand_id": self.strand_id,
            "strand_hash": self.strand_hash,
            "lines": [line.canonical() for line in self.lines],
        }


def build_line(
    *,
    line_number: int,
    row: int,
    position: int,
    x: int,
    authority_symbol: str,
    previous_line_hash: str = "0" * 64,
    rule: ABAuthorityRule | None = None,
) -> ABLine:
    rule = rule or ABAuthorityRule()
    a_symbol, b_symbol = rule.resolve(x=x, authority_symbol=authority_symbol)
    return ABLine(
        line_number=line_number,
        row=row,
        position=position,
        x=x,
        authority_symbol=authority_symbol,
        a_symbol=a_symbol,
        b_symbol=b_symbol,
        previous_line_hash=previous_line_hash,
    )


def build_line_strand(
    lines: Iterable[tuple[int, int, int, str]],
    *,
    strand_id: str,
    rule: ABAuthorityRule | None = None,
) -> ABLineStrand:
    """Build from (row, position, x, authority_symbol) tuples.

    Authority is explicit per line. The runtime does not infer a BODMAS step.
    """
    rule = rule or ABAuthorityRule()
    previous = "0" * 64
    built = []
    for line_number, (row, position, x, authority_symbol) in enumerate(lines, start=1):
        line = build_line(
            line_number=line_number,
            row=row,
            position=position,
            x=x,
            authority_symbol=authority_symbol,
            previous_line_hash=previous,
            rule=rule,
        )
        built.append(line)
        previous = line.line_hash
    return ABLineStrand(strand_id=strand_id, lines=tuple(built))


def line_to_line_possibilities(
    previous_line: ABLine | None,
    *,
    next_line_number: int,
    row: int,
    position: int,
    x: int,
    rule: ABAuthorityRule | None = None,
) -> Tuple[ABLine, ...]:
    """Enumerate valid next-line branches under the defined authority chain.

    No branch is promoted to authoritative execution by this function.
    """
    rule = rule or ABAuthorityRule()
    previous_hash = previous_line.line_hash if previous_line else "0" * 64
    return tuple(
        build_line(
            line_number=next_line_number,
            row=row,
            position=position,
            x=x,
            authority_symbol=authority,
            previous_line_hash=previous_hash,
            rule=rule,
        )
        for authority in rule.authority_chain
    )
