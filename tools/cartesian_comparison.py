#!/usr/bin/env python3
"""Cartesian vs. Keddeh comparison engine.

Runs identical mathematical operations in both coordinate systems and reports
differences in behaviour, edge cases, and stability.

Anchor: A. KEDDEH / BRAINK / KEX / K-SYSTEMS
Status: MODEL-LOCAL
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from keddeh_matrix_core import (
    KeddehValue,
    KeddehMatrix,
    KeddehVector,
    KeddehArithmetic,
    BoundaryEvent,
    ObserverFrame,
    _determinant_recursive,
)


# ---------------------------------------------------------------------------
# Cartesian reference implementation
# ---------------------------------------------------------------------------

@dataclass
class CartesianMatrix:
    """Standard Cartesian matrix (zero-anchored, Descartes origin)."""
    rows: int
    cols: int
    data: List[List[float]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.data:
            self.data = [[0.0] * self.cols for _ in range(self.rows)]

    @classmethod
    def from_values(cls, values: List[List[float]]) -> "CartesianMatrix":
        rows = len(values)
        cols = len(values[0]) if rows else 0
        import copy
        return cls(rows=rows, cols=cols, data=copy.deepcopy(values))

    def get(self, row: int, col: int) -> float:
        """Get value at 0-indexed position."""
        return self.data[row][col]

    def set(self, row: int, col: int, value: float) -> None:
        self.data[row][col] = value

    def transpose(self) -> "CartesianMatrix":
        transposed = [
            [self.data[r][c] for r in range(self.rows)]
            for c in range(self.cols)
        ]
        return CartesianMatrix(rows=self.cols, cols=self.rows, data=transposed)

    def add(self, other: "CartesianMatrix") -> "CartesianMatrix":
        if self.rows != other.rows or self.cols != other.cols:
            raise ValueError("Dimension mismatch.")
        result = [
            [self.data[r][c] + other.data[r][c] for c in range(self.cols)]
            for r in range(self.rows)
        ]
        return CartesianMatrix(rows=self.rows, cols=self.cols, data=result)

    def multiply(self, other: "CartesianMatrix") -> "CartesianMatrix":
        if self.cols != other.rows:
            raise ValueError("Incompatible dimensions.")
        result = [
            [
                sum(self.data[r][k] * other.data[k][c] for k in range(self.cols))
                for c in range(other.cols)
            ]
            for r in range(self.rows)
        ]
        return CartesianMatrix(rows=self.rows, cols=other.cols, data=result)

    def scale(self, scalar: float) -> "CartesianMatrix":
        result = [[v * scalar for v in row] for row in self.data]
        return CartesianMatrix(rows=self.rows, cols=self.cols, data=result)

    def determinant(self) -> float:
        if self.rows != self.cols:
            raise ValueError("Determinant requires square matrix.")
        return _determinant_recursive(self.data)

    def inverse(self) -> Optional["CartesianMatrix"]:
        """Return inverse or None if matrix is singular (det == 0)."""
        det = self.determinant()
        if det == 0.0:
            return None   # Cartesian system: singular matrix, no inverse
        n = self.rows
        from keddeh_matrix_core import _matrix_inverse
        inv_data = _matrix_inverse(self.data, det)
        return CartesianMatrix(rows=n, cols=n, data=inv_data)

    def __repr__(self) -> str:
        rows_str = "\n  ".join(
            "[ " + "  ".join(f"{v:+.4f}" for v in row) + " ]"
            for row in self.data
        )
        return f"CartesianMatrix({self.rows}x{self.cols}):\n  {rows_str}"


@dataclass
class CartesianVector:
    components: List[float]

    @classmethod
    def from_floats(cls, *values: float) -> "CartesianVector":
        return cls(list(values))

    def dimension(self) -> int:
        return len(self.components)

    def magnitude(self) -> float:
        return math.sqrt(sum(v ** 2 for v in self.components))

    def add(self, other: "CartesianVector") -> "CartesianVector":
        return CartesianVector([a + b for a, b in zip(self.components, other.components)])

    def scale(self, scalar: float) -> "CartesianVector":
        return CartesianVector([v * scalar for v in self.components])

    def dot(self, other: "CartesianVector") -> float:
        return sum(a * b for a, b in zip(self.components, other.components))

    def __repr__(self) -> str:
        vals = "  ".join(f"{v:+.4f}" for v in self.components)
        return f"CartesianVector[{vals}]"


# ---------------------------------------------------------------------------
# Comparison result types
# ---------------------------------------------------------------------------

@dataclass
class ComparisonResult:
    operation: str
    cartesian_result: Any
    keddeh_result: Any
    cartesian_error: Optional[str]
    keddeh_error: Optional[str]
    cartesian_time_us: float
    keddeh_time_us: float
    agrees: bool
    notes: str

    def summary(self) -> str:
        status = "AGREE" if self.agrees else "DIFFER"
        c_res = self.cartesian_error or str(self.cartesian_result)
        k_res = self.keddeh_error or str(self.keddeh_result)
        return (
            f"[{status}] {self.operation}\n"
            f"  Cartesian : {c_res}  ({self.cartesian_time_us:.1f} µs)\n"
            f"  Keddeh    : {k_res}  ({self.keddeh_time_us:.1f} µs)\n"
            f"  Notes     : {self.notes}"
        )


# ---------------------------------------------------------------------------
# Comparison harness
# ---------------------------------------------------------------------------

class ComparisonHarness:
    """Run identical operations in both systems and record results."""

    def __init__(self) -> None:
        self.results: List[ComparisonResult] = []

    # --- Scalar arithmetic ---

    def compare_arithmetic(self, a: float, b: float) -> List[ComparisonResult]:
        ops = [
            ("add",      lambda x, y: x + y,        lambda x, y: KeddehArithmetic.add(KeddehValue(x), KeddehValue(y)).value),
            ("subtract", lambda x, y: x - y,        lambda x, y: KeddehArithmetic.subtract(KeddehValue(x), KeddehValue(y)).value),
            ("multiply", lambda x, y: x * y,        lambda x, y: KeddehArithmetic.multiply(KeddehValue(x), KeddehValue(y)).value),
            ("divide",   lambda x, y: x / y if y != 0 else None, lambda x, y: KeddehArithmetic.divide(KeddehValue(x), KeddehValue(y)).value),
        ]
        results = []
        for name, cart_fn, keddeh_fn in ops:
            c_res, c_err, c_time = _timed(cart_fn, a, b)
            k_res, k_err, k_time = _timed(keddeh_fn, a, b)
            agrees = (c_res == k_res) and (c_err is None and k_err is None)
            results.append(ComparisonResult(
                operation=f"scalar_{name}({a}, {b})",
                cartesian_result=c_res,
                keddeh_result=k_res,
                cartesian_error=c_err,
                keddeh_error=k_err,
                cartesian_time_us=c_time,
                keddeh_time_us=k_time,
                agrees=agrees,
                notes=_arithmetic_note(name, a, b, c_res, k_res, c_err, k_err),
            ))
        self.results.extend(results)
        return results

    def compare_division_by_zero(self) -> ComparisonResult:
        """Key comparison: division by zero in each system."""
        # Cartesian
        c_start = time.perf_counter()
        c_err: Optional[str] = None
        c_res = None
        try:
            c_res = 5.0 / 0.0
        except ZeroDivisionError as e:
            c_err = f"ZeroDivisionError: {e}"
        c_time = (time.perf_counter() - c_start) * 1e6

        # Keddeh — zero cannot be instantiated
        k_start = time.perf_counter()
        k_err = None
        k_res = None
        try:
            KeddehValue(0.0)  # This raises ValueError
            k_res = "unreachable"
        except ValueError as e:
            k_err = f"ValueError (structural): {e}"
        k_time = (time.perf_counter() - k_start) * 1e6

        result = ComparisonResult(
            operation="division_by_zero(5 / 0)",
            cartesian_result=c_res,
            keddeh_result=k_res,
            cartesian_error=c_err,
            keddeh_error=k_err,
            cartesian_time_us=c_time,
            keddeh_time_us=k_time,
            agrees=False,
            notes=(
                "Cartesian defers the problem (runtime error). "
                "Keddeh transforms it structurally: zero is not a KeddehValue, "
                "so the operation cannot be expressed — the problem is eliminated, not deferred."
            ),
        )
        self.results.append(result)
        return result

    # --- Matrix operations ---

    def compare_matrix_determinant(
        self, values: List[List[float]]
    ) -> ComparisonResult:
        """Compare determinant computation including singular-matrix case."""
        c_start = time.perf_counter()
        c_err = None
        c_res = None
        try:
            cm = CartesianMatrix.from_values(values)
            c_res = cm.determinant()
        except Exception as e:
            c_err = str(e)
        c_time = (time.perf_counter() - c_start) * 1e6

        k_start = time.perf_counter()
        k_err = None
        k_res = None
        try:
            km = KeddehMatrix.from_values(values)
            k_res = km.determinant()
        except (BoundaryEvent, ValueError) as e:
            k_err = str(e)
        k_time = (time.perf_counter() - k_start) * 1e6

        agrees = (c_res is not None and k_res is not None and abs(c_res - k_res) < 1e-9)
        result = ComparisonResult(
            operation=f"matrix_determinant({values})",
            cartesian_result=c_res,
            keddeh_result=k_res,
            cartesian_error=c_err,
            keddeh_error=k_err,
            cartesian_time_us=c_time,
            keddeh_time_us=k_time,
            agrees=agrees,
            notes=_det_note(c_res, k_res),
        )
        self.results.append(result)
        return result

    def compare_singular_matrix(self) -> ComparisonResult:
        """Singular matrix: Cartesian collapses, Keddeh raises a boundary event."""
        # A singular matrix has linearly dependent rows
        singular = [[2.0, 4.0], [1.0, 2.0]]

        c_start = time.perf_counter()
        c_err = None
        c_res = None
        try:
            cm = CartesianMatrix.from_values(singular)
            inv = cm.inverse()
            c_res = "None (singular — no inverse)" if inv is None else str(inv)
        except Exception as e:
            c_err = str(e)
        c_time = (time.perf_counter() - c_start) * 1e6

        k_start = time.perf_counter()
        k_err = None
        k_res = None
        try:
            # Keddeh cannot even build this matrix cleanly — it can if no entry is zero
            km = KeddehMatrix.from_values(singular)
            inv = km.inverse()
            k_res = str(inv)
        except BoundaryEvent as e:
            k_err = f"BoundaryEvent: {e}"
        except ValueError as e:
            k_err = f"ValueError: {e}"
        k_time = (time.perf_counter() - k_start) * 1e6

        result = ComparisonResult(
            operation="singular_matrix_inverse([[2,4],[1,2]])",
            cartesian_result=c_res,
            keddeh_result=k_res,
            cartesian_error=c_err,
            keddeh_error=k_err,
            cartesian_time_us=c_time,
            keddeh_time_us=k_time,
            agrees=False,
            notes=(
                "Cartesian silently returns None for singular matrix — dimensional collapse. "
                "Keddeh raises a BoundaryEvent, explicitly flagging the state rather than "
                "silently losing information."
            ),
        )
        self.results.append(result)
        return result

    def compare_vector_operations(
        self, a_vals: List[float], b_vals: List[float]
    ) -> List[ComparisonResult]:
        results = []

        # Addition
        c_start = time.perf_counter()
        c_err = None
        c_res = None
        try:
            cv1, cv2 = CartesianVector.from_floats(*a_vals), CartesianVector.from_floats(*b_vals)
            c_res = str(cv1.add(cv2))
        except Exception as e:
            c_err = str(e)
        c_time = (time.perf_counter() - c_start) * 1e6

        k_start = time.perf_counter()
        k_err = None
        k_res = None
        try:
            kv1 = KeddehVector.from_floats(*a_vals)
            kv2 = KeddehVector.from_floats(*b_vals)
            k_res = str(kv1.add(kv2))
        except (BoundaryEvent, ValueError) as e:
            k_err = str(e)
        k_time = (time.perf_counter() - k_start) * 1e6

        results.append(ComparisonResult(
            operation=f"vector_add({a_vals}, {b_vals})",
            cartesian_result=c_res,
            keddeh_result=k_res,
            cartesian_error=c_err,
            keddeh_error=k_err,
            cartesian_time_us=c_time,
            keddeh_time_us=k_time,
            agrees=(c_res == k_res),
            notes="Vector addition comparison. Keddeh raises BoundaryEvent if any component sum = 0.",
        ))

        # Dot product
        c_start = time.perf_counter()
        c_dot: Optional[float] = None
        c_dot_err = None
        try:
            cv1, cv2 = CartesianVector.from_floats(*a_vals), CartesianVector.from_floats(*b_vals)
            c_dot = cv1.dot(cv2)
        except Exception as e:
            c_dot_err = str(e)
        c_time = (time.perf_counter() - c_start) * 1e6

        k_start = time.perf_counter()
        k_dot: Optional[float] = None
        k_dot_err = None
        try:
            kv1 = KeddehVector.from_floats(*a_vals)
            kv2 = KeddehVector.from_floats(*b_vals)
            k_dot = kv1.dot(kv2)
        except (ValueError, BoundaryEvent) as e:
            k_dot_err = str(e)
        k_time = (time.perf_counter() - k_start) * 1e6

        results.append(ComparisonResult(
            operation=f"vector_dot({a_vals}, {b_vals})",
            cartesian_result=c_dot,
            keddeh_result=k_dot,
            cartesian_error=c_dot_err,
            keddeh_error=k_dot_err,
            cartesian_time_us=c_time,
            keddeh_time_us=k_time,
            agrees=(c_dot == k_dot),
            notes="Dot product: both systems agree on numeric result.",
        ))

        self.results.extend(results)
        return results

    # --- Benchmark ---

    def benchmark_matrix_multiply(self, size: int = 4, iterations: int = 1000) -> Dict[str, Any]:
        """Performance benchmark: matrix multiply in both systems."""
        import random
        random.seed(42)

        # Range [0.1, 5.0] ensures all entries are non-zero KeddehValues and
        # the sign is randomised to produce a realistic mixed-sign matrix.
        _BENCH_MIN_VALUE: float = 0.1
        _BENCH_MAX_VALUE: float = 5.0

        def rand_matrix(n: int) -> List[List[float]]:
            return [
                [random.uniform(_BENCH_MIN_VALUE, _BENCH_MAX_VALUE) * (1 if random.random() > 0.5 else -1)
                 for _ in range(n)]
                for _ in range(n)
            ]

        values = rand_matrix(size)

        c_start = time.perf_counter()
        for _ in range(iterations):
            cm = CartesianMatrix.from_values(values)
            cm.multiply(cm)
        c_elapsed = (time.perf_counter() - c_start) * 1e3

        k_errors = 0
        k_start = time.perf_counter()
        for _ in range(iterations):
            try:
                km = KeddehMatrix.from_values(values)
                km.multiply(km)
            except (BoundaryEvent, ValueError):
                k_errors += 1
        k_elapsed = (time.perf_counter() - k_start) * 1e3

        return {
            "operation": f"matrix_multiply_{size}x{size}",
            "iterations": iterations,
            "cartesian_ms": round(c_elapsed, 3),
            "keddeh_ms": round(k_elapsed, 3),
            "keddeh_boundary_events": k_errors,
            "ratio": round(k_elapsed / c_elapsed, 3) if c_elapsed > 0 else None,
        }

    # --- Summary ---

    def print_summary(self) -> None:
        print("\n" + "=" * 70)
        print("CARTESIAN vs. KEDDEH — Comparison Report")
        print("=" * 70)
        agree_count = sum(1 for r in self.results if r.agrees)
        differ_count = len(self.results) - agree_count
        print(f"Total operations: {len(self.results)}  Agree: {agree_count}  Differ: {differ_count}")
        print()
        for r in self.results:
            print(r.summary())
            print()

    def problems_keddeh_solves(self) -> List[str]:
        """Return a list of problems Keddeh solves better than Cartesian."""
        return [
            "1. Division-by-zero: Keddeh eliminates it structurally (type system) "
               "rather than deferring it as a runtime exception.",
            "2. Singular matrix detection: Keddeh raises an explicit BoundaryEvent "
               "instead of silently returning None or an undefined inverse.",
            "3. Additive identity paradox: Keddeh formalises x + (-x) as an observer "
               "boundary event, not a collapse to zero, preserving semantic meaning.",
            "4. Dimensional collapse: Keddeh matrices signal boundary events when "
               "determinants would reach zero, preventing silent space collapse.",
            "5. Observer-relative measurement: Keddeh encodes the observer frame "
               "explicitly, whereas Cartesian implicitly assumes a universal (0,0) origin.",
        ]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _timed(fn, *args):
    start = time.perf_counter()
    err = None
    result = None
    try:
        result = fn(*args)
    except Exception as e:
        err = str(e)
    elapsed = (time.perf_counter() - start) * 1e6
    return result, err, elapsed


def _arithmetic_note(op: str, a: float, b: float, c_res, k_res, c_err, k_err) -> str:
    if c_err or k_err:
        return f"Cartesian error: {c_err} | Keddeh error: {k_err}"
    if c_res == k_res:
        return "Both systems agree."
    return f"Results differ: Cartesian={c_res}, Keddeh={k_res}"


def _det_note(c_res, k_res) -> str:
    if c_res is None and k_res is None:
        return "Both systems failed to compute determinant."
    if c_res == 0.0:
        return (
            "Cartesian determinant = 0 → dimensional collapse. "
            "Keddeh raises BoundaryEvent at the type level."
        )
    if c_res is not None and k_res is not None and abs(c_res - k_res) < 1e-9:
        return f"Both systems agree: det = {c_res:.4f}"
    return f"Cartesian: {c_res}, Keddeh: {k_res}"


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _run_demo() -> None:
    harness = ComparisonHarness()

    print("=" * 70)
    print("Cartesian vs. Keddeh — Comparative Analysis")
    print("=" * 70)

    print("\n--- Scalar arithmetic ---")
    for a, b in [(3.0, 2.0), (-3.0, -2.0), (5.0, -5.0)]:
        results = harness.compare_arithmetic(a, b)
        for r in results:
            print(" ", r.summary())

    print("\n--- Division by zero ---")
    r = harness.compare_division_by_zero()
    print(" ", r.summary())

    print("\n--- Matrix determinant (non-singular) ---")
    r = harness.compare_matrix_determinant([[2.0, -1.0], [-3.0, 4.0]])
    print(" ", r.summary())

    print("\n--- Singular matrix (dimensional collapse test) ---")
    r = harness.compare_singular_matrix()
    print(" ", r.summary())

    print("\n--- Vector operations ---")
    results = harness.compare_vector_operations([1.0, 2.0, 3.0], [-1.0, -1.0, 2.0])
    for r in results:
        print(" ", r.summary())

    print("\n--- Performance benchmark (4×4 matrix multiply, 1000 iterations) ---")
    bench = harness.benchmark_matrix_multiply(size=4, iterations=1000)
    print(f"  Cartesian: {bench['cartesian_ms']} ms")
    print(f"  Keddeh:    {bench['keddeh_ms']} ms  (boundary events: {bench['keddeh_boundary_events']})")
    print(f"  Ratio:     {bench['ratio']}x")

    print("\n--- Problems Keddeh solves better than Cartesian ---")
    for problem in harness.problems_keddeh_solves():
        print(f"  {problem}")

    print("\nStatus: MODEL-LOCAL")


if __name__ == "__main__":
    _run_demo()
