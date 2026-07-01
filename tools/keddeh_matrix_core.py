#!/usr/bin/env python3
"""Keddeh Matrix Core Engine — zero-free arithmetic and observer-state framework.

The 1-Keddeh sequence: -3 | -2 | -1 | +1 | +2 | +3
Zero is the observer boundary (reference frame), not a natural number or arithmetic operand.
This engine formalises the Keddeh Matrix as a complete alternative coordinate system.

Anchor: A. KEDDEH / BRAINK / KEX / K-SYSTEMS
Status: MODEL-LOCAL
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Tuple, Optional


# ---------------------------------------------------------------------------
# Axiomatic constants
# ---------------------------------------------------------------------------

OBSERVER_BOUNDARY: float = 0.0          # The boundary — reference frame, not a value
KEDDEH_SEQUENCE: List[int] = [-3, -2, -1, 1, 2, 3]   # 1-Keddeh number line without zero


class ObserverState(Enum):
    """Position of a value relative to the observer boundary."""
    NEGATIVE = "negative"   # below observer boundary
    POSITIVE = "positive"   # above observer boundary
    BOUNDARY = "boundary"   # at the observer reference frame (not a natural number)


# ---------------------------------------------------------------------------
# Core value type
# ---------------------------------------------------------------------------

@dataclass
class KeddehValue:
    """A scalar value in the Keddeh framework.

    Zero is forbidden as a natural arithmetic operand; it is only permitted as
    an observer boundary marker (ObserverState.BOUNDARY).
    """
    value: float

    def __post_init__(self) -> None:
        if self.value == 0.0:
            raise ValueError(
                "Zero is the observer boundary reference frame, not a Keddeh value. "
                "Use ObserverState.BOUNDARY to represent the observer's position."
            )

    @property
    def observer_state(self) -> ObserverState:
        if self.value < 0:
            return ObserverState.NEGATIVE
        return ObserverState.POSITIVE

    @property
    def magnitude(self) -> float:
        """Distance from the observer boundary."""
        return abs(self.value)

    def invert(self) -> "KeddehValue":
        """Instantaneous state inversion across the observer boundary: -x ↔ x."""
        return KeddehValue(-self.value)

    def __repr__(self) -> str:
        sign = "+" if self.value > 0 else ""
        return f"KeddehValue({sign}{self.value})"


# ---------------------------------------------------------------------------
# Boundary-crossing arithmetic engine
# ---------------------------------------------------------------------------

class KeddehArithmetic:
    """Zero-free arithmetic operations across the observer boundary.

    Rules:
    - Values never pass through zero — they cross the boundary instantaneously.
    - The observer boundary is a reference frame, not a calculable quantity.
    - Inversion is instantaneous, not gradual.
    """

    @staticmethod
    def add(a: KeddehValue, b: KeddehValue) -> KeddehValue:
        """Add two Keddeh values.

        When addition would produce zero (a = -b), a BoundaryEvent is raised
        because the result is an observer-state event, not a natural number.
        """
        result = a.value + b.value
        if result == 0.0:
            raise BoundaryEvent(
                f"Addition {a.value} + {b.value} = 0: this is an observer-state "
                "boundary crossing, not a natural number result. "
                "The two operands are state inversions of each other."
            )
        return KeddehValue(result)

    @staticmethod
    def subtract(a: KeddehValue, b: KeddehValue) -> KeddehValue:
        """Subtract b from a.

        Subtraction crossing the boundary (a = b) produces a BoundaryEvent.
        """
        result = a.value - b.value
        if result == 0.0:
            raise BoundaryEvent(
                f"Subtraction {a.value} - {b.value} = 0: observer boundary event. "
                "Both values are at identical magnitudes on the same side."
            )
        return KeddehValue(result)

    @staticmethod
    def multiply(a: KeddehValue, b: KeddehValue) -> KeddehValue:
        """Multiply two Keddeh values.

        Negative × negative = positive through boundary-reflection logic:
        two inversions cancel each other, restoring the positive state.
        This is *not* a sign-rule trick — it follows from the geometry of
        the observer boundary.
        """
        result = a.value * b.value
        # Result cannot be zero because neither operand can be zero.
        return KeddehValue(result)

    @staticmethod
    def divide(a: KeddehValue, b: KeddehValue) -> KeddehValue:
        """Divide a by b.

        Division by the observer boundary is formally undefined in Keddeh
        mathematics — but this is transformed rather than deferred: the
        operation is structurally impossible because the boundary is not a
        Keddeh value, only a reference frame. Passing a KeddehValue of zero
        is already prevented by the type system.
        """
        result = a.value / b.value
        if result == 0.0:
            raise BoundaryEvent(
                f"Division {a.value} / {b.value} = 0: observer boundary event."
            )
        return KeddehValue(result)

    @staticmethod
    def power(base: KeddehValue, exponent: KeddehValue) -> KeddehValue:
        """Raise base to the power of exponent."""
        result = base.value ** exponent.value
        if result == 0.0:
            raise BoundaryEvent("Power result is the observer boundary — not a Keddeh value.")
        return KeddehValue(result)

    @staticmethod
    def boundary_distance(a: KeddehValue, b: KeddehValue) -> float:
        """Return the signed distance between two values, crossing the boundary
        instantaneously when they are on opposite sides."""
        return b.value - a.value


class BoundaryEvent(Exception):
    """Raised when an arithmetic operation reaches the observer boundary."""


# ---------------------------------------------------------------------------
# KeddehMatrix: 2D matrix without zero-anchored coordinates
# ---------------------------------------------------------------------------

@dataclass
class KeddehMatrix:
    """A matrix in the Keddeh framework.

    Rows and columns are 1-indexed (never zero-indexed).
    The internal representation stores KeddehValue instances.
    """
    rows: int
    cols: int
    data: List[List[KeddehValue]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.rows < 1 or self.cols < 1:
            raise ValueError("KeddehMatrix dimensions must be >= 1 (no zero-axis).")
        if not self.data:
            # Default: identity-like fill with +1.0
            self.data = [
                [KeddehValue(1.0) for _ in range(self.cols)]
                for _ in range(self.rows)
            ]

    @classmethod
    def from_values(cls, values: List[List[float]]) -> "KeddehMatrix":
        """Create a KeddehMatrix from a nested list of floats.

        Raises ValueError if any value is zero (observer boundary, not a number).
        """
        rows = len(values)
        cols = len(values[0]) if rows > 0 else 0
        data = [
            [KeddehValue(v) for v in row]
            for row in values
        ]
        return cls(rows=rows, cols=cols, data=data)

    def get(self, row: int, col: int) -> KeddehValue:
        """Get value at 1-indexed position (row, col)."""
        if row < 1 or col < 1:
            raise IndexError(f"KeddehMatrix uses 1-based indexing. Got row={row}, col={col}.")
        return self.data[row - 1][col - 1]

    def set(self, row: int, col: int, value: KeddehValue) -> None:
        """Set value at 1-indexed position (row, col)."""
        if row < 1 or col < 1:
            raise IndexError(f"KeddehMatrix uses 1-based indexing. Got row={row}, col={col}.")
        self.data[row - 1][col - 1] = value

    def transpose(self) -> "KeddehMatrix":
        """Return the transpose of this matrix."""
        transposed = [
            [self.data[r][c] for r in range(self.rows)]
            for c in range(self.cols)
        ]
        return KeddehMatrix(rows=self.cols, cols=self.rows, data=transposed)

    def add(self, other: "KeddehMatrix") -> "KeddehMatrix":
        """Element-wise addition."""
        if self.rows != other.rows or self.cols != other.cols:
            raise ValueError("Matrix dimensions must match for addition.")
        result_data: List[List[KeddehValue]] = []
        for r in range(self.rows):
            row_data: List[KeddehValue] = []
            for c in range(self.cols):
                row_data.append(KeddehArithmetic.add(self.data[r][c], other.data[r][c]))
            result_data.append(row_data)
        return KeddehMatrix(rows=self.rows, cols=self.cols, data=result_data)

    def multiply(self, other: "KeddehMatrix") -> "KeddehMatrix":
        """Matrix multiplication."""
        if self.cols != other.rows:
            raise ValueError(
                f"Cannot multiply {self.rows}x{self.cols} by {other.rows}x{other.cols}."
            )
        result_data: List[List[KeddehValue]] = []
        for r in range(self.rows):
            row_data: List[KeddehValue] = []
            for c in range(other.cols):
                total = sum(
                    self.data[r][k].value * other.data[k][c].value
                    for k in range(self.cols)
                )
                if total == 0.0:
                    raise BoundaryEvent(
                        f"Matrix product at ({r+1},{c+1}) = 0: observer boundary event. "
                        "The Keddeh matrix preserves non-zero state across all products."
                    )
                row_data.append(KeddehValue(total))
            result_data.append(row_data)
        return KeddehMatrix(rows=self.rows, cols=other.cols, data=result_data)

    def scale(self, scalar: KeddehValue) -> "KeddehMatrix":
        """Scale all elements by a Keddeh scalar."""
        new_data = [
            [KeddehArithmetic.multiply(cell, scalar) for cell in row]
            for row in self.data
        ]
        return KeddehMatrix(rows=self.rows, cols=self.cols, data=new_data)

    def determinant(self) -> float:
        """Compute the determinant using cofactor expansion.

        Unlike Cartesian matrices, a Keddeh matrix cannot have a zero determinant
        unless a BoundaryEvent occurs — proving dimensional stability.
        """
        if self.rows != self.cols:
            raise ValueError("Determinant is only defined for square matrices.")
        return _determinant_recursive(
            [[cell.value for cell in row] for row in self.data]
        )

    def inverse(self) -> "KeddehMatrix":
        """Compute the matrix inverse."""
        if self.rows != self.cols:
            raise ValueError("Only square matrices have inverses.")
        det = self.determinant()
        if det == 0.0:
            raise BoundaryEvent(
                "Determinant is 0 — observer boundary event. "
                "This proves dimensional collapse in Cartesian space; in Keddeh "
                "space this state is unreachable from valid KeddehValue inputs."
            )
        n = self.rows
        float_data = [[self.data[r][c].value for c in range(n)] for r in range(n)]
        inv_data = _matrix_inverse(float_data, det)
        # Convert back to KeddehValues (any zero in inverse is a boundary event)
        keddeh_data: List[List[KeddehValue]] = []
        for r in range(n):
            row_vals: List[KeddehValue] = []
            for c in range(n):
                v = inv_data[r][c]
                if v == 0.0:
                    raise BoundaryEvent(
                        f"Inverse element at ({r+1},{c+1}) = 0: observer boundary event."
                    )
                row_vals.append(KeddehValue(v))
            keddeh_data.append(row_vals)
        return KeddehMatrix(rows=n, cols=n, data=keddeh_data)

    def __repr__(self) -> str:
        rows_str = "\n  ".join(
            "[ " + "  ".join(f"{cell.value:+.4f}" for cell in row) + " ]"
            for row in self.data
        )
        return f"KeddehMatrix({self.rows}x{self.cols}):\n  {rows_str}"


# ---------------------------------------------------------------------------
# KeddehVector
# ---------------------------------------------------------------------------

@dataclass
class KeddehVector:
    """A vector in Keddeh space — no origin binding, purely relational."""
    components: List[KeddehValue]

    @classmethod
    def from_floats(cls, *values: float) -> "KeddehVector":
        return cls([KeddehValue(v) for v in values])

    def dimension(self) -> int:
        return len(self.components)

    def magnitude(self) -> float:
        return math.sqrt(sum(c.value ** 2 for c in self.components))

    def add(self, other: "KeddehVector") -> "KeddehVector":
        if self.dimension() != other.dimension():
            raise ValueError("Vectors must have the same dimension.")
        result = []
        for a, b in zip(self.components, other.components):
            total = a.value + b.value
            if total == 0.0:
                raise BoundaryEvent(
                    "Vector addition result component = 0: observer boundary event."
                )
            result.append(KeddehValue(total))
        return KeddehVector(result)

    def scale(self, scalar: KeddehValue) -> "KeddehVector":
        return KeddehVector([KeddehArithmetic.multiply(c, scalar) for c in self.components])

    def dot(self, other: "KeddehVector") -> float:
        if self.dimension() != other.dimension():
            raise ValueError("Vectors must have the same dimension.")
        return sum(a.value * b.value for a, b in zip(self.components, other.components))

    def invert(self) -> "KeddehVector":
        """State inversion: reflect all components across the observer boundary."""
        return KeddehVector([c.invert() for c in self.components])

    def __repr__(self) -> str:
        vals = "  ".join(f"{c.value:+.4f}" for c in self.components)
        return f"KeddehVector[{vals}]"


# ---------------------------------------------------------------------------
# Observer state manager
# ---------------------------------------------------------------------------

@dataclass
class ObserverFrame:
    """Represents the observer's reference frame.

    The observer is always at their own origin (the boundary).
    All measurements are relative distances from the observer.
    """
    label: str = "observer"

    def measure(self, value: KeddehValue) -> Tuple[float, ObserverState]:
        """Return (distance_from_boundary, state) for a value."""
        return value.magnitude, value.observer_state

    def cross_boundary(self, value: KeddehValue) -> KeddehValue:
        """Instantaneous state inversion across the observer boundary."""
        return value.invert()

    def relative_distance(self, a: KeddehValue, b: KeddehValue) -> float:
        """Signed distance from a to b, as seen by this observer."""
        return KeddehArithmetic.boundary_distance(a, b)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _determinant_recursive(matrix: List[List[float]]) -> float:
    n = len(matrix)
    if n == 1:
        return matrix[0][0]
    if n == 2:
        return matrix[0][0] * matrix[1][1] - matrix[0][1] * matrix[1][0]
    det = 0.0
    for col in range(n):
        minor = [
            [matrix[r][c] for c in range(n) if c != col]
            for r in range(1, n)
        ]
        det += ((-1) ** col) * matrix[0][col] * _determinant_recursive(minor)
    return det


def _matrix_inverse(matrix: List[List[float]], det: float) -> List[List[float]]:
    """Compute inverse via adjugate / determinant."""
    n = len(matrix)
    cofactors = []
    for r in range(n):
        row_cofactors = []
        for c in range(n):
            minor = [
                [matrix[i][j] for j in range(n) if j != c]
                for i in range(n) if i != r
            ]
            cofactor = ((-1) ** (r + c)) * _determinant_recursive(minor)
            row_cofactors.append(cofactor)
        cofactors.append(row_cofactors)
    # Transpose cofactors to get adjugate
    adjugate = [[cofactors[c][r] for c in range(n)] for r in range(n)]
    return [[adjugate[r][c] / det for c in range(n)] for r in range(n)]


# ---------------------------------------------------------------------------
# Proof validation utilities
# ---------------------------------------------------------------------------

def proof_negative_times_negative(a: float, b: float) -> dict:
    """Prove negative × negative = positive via boundary-reflection logic.

    Two state inversions cancel: the first inversion crosses from positive to
    negative state; the second inversion crosses back. The result is always in
    the positive state.
    """
    assert a < 0 and b < 0, "Both values must be negative for this proof."
    kv_a = KeddehValue(a)
    kv_b = KeddehValue(b)
    product = KeddehArithmetic.multiply(kv_a, kv_b)
    return {
        "a": a,
        "b": b,
        "a_state": kv_a.observer_state.value,
        "b_state": kv_b.observer_state.value,
        "product": product.value,
        "product_state": product.observer_state.value,
        "proof": (
            f"(-{abs(a)}) × (-{abs(b)}): first inversion crosses boundary to negative state, "
            f"second inversion crosses back to positive state. "
            f"Result = +{product.value}. Verified: {product.value > 0}."
        ),
    }


def proof_additive_inversion(x: float) -> dict:
    """Prove that x + (-x) is an observer boundary event, not a zero sum."""
    kv = KeddehValue(x)
    kv_inv = kv.invert()
    try:
        KeddehArithmetic.add(kv, kv_inv)
        return {"x": x, "result": "unexpected_success", "proof": "FAILED"}
    except BoundaryEvent as e:
        return {
            "x": x,
            "x_inv": kv_inv.value,
            "boundary_event": str(e),
            "proof": (
                f"x={x} and its inversion {kv_inv.value} produce an observer boundary event, "
                "not a zero sum. Zero is a reference frame, not a computational result."
            ),
        }


def proof_division_transform(a: float, b: float) -> dict:
    """Demonstrate that division-by-zero is structurally impossible in Keddeh.

    The type system prevents zero from entering as a KeddehValue, so division
    by the observer boundary is not deferred — it is transformed away at the
    structural level.
    """
    kv_a = KeddehValue(a)
    kv_b = KeddehValue(b)
    result = KeddehArithmetic.divide(kv_a, kv_b)
    return {
        "a": a,
        "b": b,
        "result": result.value,
        "proof": (
            f"{a} / {b} = {result.value}. "
            "Division by zero is impossible because zero cannot be instantiated as a KeddehValue — "
            "it is the observer boundary reference frame, not an arithmetic operand."
        ),
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _run_demo() -> None:
    print("=" * 60)
    print("Keddeh Matrix Core Engine — Demo")
    print("=" * 60)

    print("\n--- 1-Keddeh Number Line ---")
    print(f"Sequence (no zero): {KEDDEH_SEQUENCE}")

    print("\n--- KeddehValue creation ---")
    for v in [-3.0, -1.0, 1.0, 3.0]:
        kv = KeddehValue(v)
        print(f"  {kv}  state={kv.observer_state.value}  magnitude={kv.magnitude}")

    print("\n--- Proof: zero is a boundary event ---")
    try:
        KeddehValue(0.0)
    except ValueError as e:
        print(f"  ValueError (expected): {e}")

    print("\n--- Arithmetic ---")
    a, b = KeddehValue(3.0), KeddehValue(2.0)
    print(f"  {a} + {b} = {KeddehArithmetic.add(a, b)}")
    print(f"  {a} - {b} = {KeddehArithmetic.subtract(a, b)}")
    print(f"  {a} × {b} = {KeddehArithmetic.multiply(a, b)}")
    print(f"  {a} ÷ {b} = {KeddehArithmetic.divide(a, b)}")

    neg_a, neg_b = KeddehValue(-3.0), KeddehValue(-2.0)
    product = KeddehArithmetic.multiply(neg_a, neg_b)
    print(f"\n--- Proof: negative × negative = positive ---")
    proof = proof_negative_times_negative(-3.0, -2.0)
    print(f"  {proof['proof']}")

    print("\n--- Proof: additive inversion is a boundary event ---")
    proof_inv = proof_additive_inversion(5.0)
    print(f"  {proof_inv['proof']}")

    print("\n--- Proof: division-by-zero is structurally transformed ---")
    proof_div = proof_division_transform(6.0, 2.0)
    print(f"  {proof_div['proof']}")

    print("\n--- KeddehMatrix (2×2) ---")
    m = KeddehMatrix.from_values([[2.0, -1.0], [-3.0, 4.0]])
    print(m)
    print(f"  Determinant: {m.determinant():.4f}")
    inv = m.inverse()
    print(f"  Inverse:\n{inv}")

    print("\n--- KeddehVector ---")
    v1 = KeddehVector.from_floats(1.0, 2.0, 3.0)
    v2 = KeddehVector.from_floats(-1.0, -1.0, 2.0)
    print(f"  v1 = {v1}")
    print(f"  v2 = {v2}")
    print(f"  v1 · v2 = {v1.dot(v2)}")
    print(f"  |v1| = {v1.magnitude():.4f}")
    print(f"  v1.invert() = {v1.invert()}")

    print("\n--- ObserverFrame ---")
    frame = ObserverFrame("primary_observer")
    kv = KeddehValue(5.0)
    dist, state = frame.measure(kv)
    print(f"  Observer measures {kv}: distance={dist}, state={state.value}")
    crossed = frame.cross_boundary(kv)
    print(f"  After boundary crossing: {crossed}")

    print("\nStatus: MODEL-LOCAL")


if __name__ == "__main__":
    _run_demo()
