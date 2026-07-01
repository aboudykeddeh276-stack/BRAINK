#!/usr/bin/env python3
"""Comprehensive test suite for the Keddeh Matrix framework.

Covers:
- Unit tests for all core operations
- Comparative benchmarks (Cartesian vs. Keddeh)
- Physical calibration validation
- Edge case handling
- Performance metrics

Anchor: A. KEDDEH / BRAINK / KEX / K-SYSTEMS
Status: MODEL-LOCAL
"""
from __future__ import annotations

import sys
import time
import traceback
from dataclasses import dataclass, field
from typing import Callable, List, Optional


# ---------------------------------------------------------------------------
# Minimal test runner (no external dependencies)
# ---------------------------------------------------------------------------

@dataclass
class TestResult:
    name: str
    passed: bool
    message: str = ""
    elapsed_us: float = 0.0

    def summary(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        msg = f"  [{status}] {self.name}"
        if self.message:
            msg += f": {self.message}"
        if self.elapsed_us > 0:
            msg += f"  ({self.elapsed_us:.1f} µs)"
        return msg


class TestSuite:
    def __init__(self, name: str) -> None:
        self.name = name
        self.results: List[TestResult] = []

    def run(self, name: str, fn: Callable[[], None]) -> TestResult:
        start = time.perf_counter()
        passed = False
        message = ""
        try:
            fn()
            passed = True
        except AssertionError as e:
            message = f"AssertionError: {e}"
        except Exception as e:
            message = f"{type(e).__name__}: {e}"
        elapsed = (time.perf_counter() - start) * 1e6
        result = TestResult(name=name, passed=passed, message=message, elapsed_us=elapsed)
        self.results.append(result)
        return result

    def print_report(self) -> int:
        passed = sum(1 for r in self.results if r.passed)
        failed = len(self.results) - passed
        print(f"\n{'='*60}")
        print(f"Suite: {self.name}")
        print(f"{'='*60}")
        print(f"Total: {len(self.results)}  Passed: {passed}  Failed: {failed}")
        for r in self.results:
            print(r.summary())
        return failed


# ---------------------------------------------------------------------------
# Import modules under test
# ---------------------------------------------------------------------------

def _import_all():
    sys.path.insert(0, __file__.rsplit("/", 1)[0])
    import keddeh_matrix_core as core
    import cartesian_comparison as cart
    import physical_calibration_tests as phys
    import geometric_transformations as geom
    import integration_virtualised_memory as vmem
    return core, cart, phys, geom, vmem


# ---------------------------------------------------------------------------
# Test suites
# ---------------------------------------------------------------------------

def suite_keddeh_value(core) -> TestSuite:
    ts = TestSuite("KeddehValue — unit tests")

    ts.run("zero_raises_ValueError", lambda: (
        _assert_raises(ValueError, lambda: core.KeddehValue(0.0))
    ))
    ts.run("positive_value_ok", lambda: (
        _assert_equal(core.KeddehValue(5.0).value, 5.0)
    ))
    ts.run("negative_value_ok", lambda: (
        _assert_equal(core.KeddehValue(-3.0).value, -3.0)
    ))
    ts.run("positive_observer_state", lambda: (
        _assert_equal(core.KeddehValue(1.0).observer_state, core.ObserverState.POSITIVE)
    ))
    ts.run("negative_observer_state", lambda: (
        _assert_equal(core.KeddehValue(-1.0).observer_state, core.ObserverState.NEGATIVE)
    ))
    ts.run("magnitude_positive", lambda: (
        _assert_close(core.KeddehValue(7.0).magnitude, 7.0)
    ))
    ts.run("magnitude_negative", lambda: (
        _assert_close(core.KeddehValue(-7.0).magnitude, 7.0)
    ))
    ts.run("invert_positive_to_negative", lambda: (
        _assert_equal(core.KeddehValue(3.0).invert().value, -3.0)
    ))
    ts.run("invert_negative_to_positive", lambda: (
        _assert_equal(core.KeddehValue(-3.0).invert().value, 3.0)
    ))
    return ts


def suite_keddeh_arithmetic(core) -> TestSuite:
    ts = TestSuite("KeddehArithmetic — unit tests")
    A = core.KeddehArithmetic
    V = core.KeddehValue

    ts.run("add_same_sign", lambda: _assert_close(A.add(V(3.0), V(2.0)).value, 5.0))
    ts.run("add_mixed_sign_no_boundary", lambda: _assert_close(A.add(V(3.0), V(-1.0)).value, 2.0))
    ts.run("add_boundary_raises", lambda: _assert_raises(core.BoundaryEvent, lambda: A.add(V(5.0), V(-5.0))))
    ts.run("subtract_positive", lambda: _assert_close(A.subtract(V(5.0), V(3.0)).value, 2.0))
    ts.run("subtract_negative", lambda: _assert_close(A.subtract(V(-3.0), V(-1.0)).value, -2.0))
    ts.run("subtract_boundary_raises", lambda: _assert_raises(core.BoundaryEvent, lambda: A.subtract(V(4.0), V(4.0))))
    ts.run("multiply_pos_pos", lambda: _assert_close(A.multiply(V(3.0), V(4.0)).value, 12.0))
    ts.run("multiply_neg_neg_positive", lambda: (
        _assert_true(A.multiply(V(-3.0), V(-4.0)).value > 0)
    ))
    ts.run("multiply_neg_neg_value", lambda: _assert_close(A.multiply(V(-3.0), V(-4.0)).value, 12.0))
    ts.run("multiply_pos_neg", lambda: _assert_close(A.multiply(V(3.0), V(-4.0)).value, -12.0))
    ts.run("divide_pos", lambda: _assert_close(A.divide(V(6.0), V(2.0)).value, 3.0))
    ts.run("divide_neg_neg", lambda: _assert_close(A.divide(V(-6.0), V(-2.0)).value, 3.0))
    ts.run("divide_boundary_raises_on_zero_result", lambda: (
        # 1e-15 is valid (exactly at epsilon boundary), and dividing by 2.0
        # produces 5e-16 which is below _BOUNDARY_EPSILON, triggering BoundaryEvent.
        _assert_raises(core.BoundaryEvent, lambda: A.divide(V(1e-15), V(2.0)))
    ))
    ts.run("boundary_distance", lambda: _assert_close(
        A.boundary_distance(V(2.0), V(5.0)), 3.0
    ))
    ts.run("boundary_distance_crossing", lambda: _assert_close(
        A.boundary_distance(V(-2.0), V(3.0)), 5.0
    ))
    return ts


def suite_keddeh_matrix(core) -> TestSuite:
    ts = TestSuite("KeddehMatrix — unit tests")
    M = core.KeddehMatrix

    ts.run("from_values_2x2", lambda: (
        _assert_equal(M.from_values([[1.0, 2.0], [3.0, 4.0]]).rows, 2)
    ))
    ts.run("from_values_zero_raises", lambda: (
        _assert_raises(ValueError, lambda: M.from_values([[0.0, 1.0], [1.0, 1.0]]))
    ))
    ts.run("1_based_get", lambda: (
        _assert_close(M.from_values([[2.0, 3.0], [4.0, 5.0]]).get(1, 1).value, 2.0)
    ))
    ts.run("0_based_get_raises", lambda: (
        _assert_raises(IndexError, lambda: M.from_values([[1.0, 2.0], [3.0, 4.0]]).get(0, 1))
    ))
    ts.run("determinant_2x2", lambda: (
        _assert_close(M.from_values([[2.0, -1.0], [-3.0, 4.0]]).determinant(), 5.0)
    ))
    ts.run("determinant_3x3", lambda: (
        _assert_close(
            M.from_values([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0], [7.0, 8.0, 9.0]]).determinant(),
            0.0,   # singular — but as float we allow here
            tol=1e-6
        )
    ))
    ts.run("inverse_2x2", lambda: (
        _assert_close(
            M.from_values([[4.0, 7.0], [2.0, 6.0]]).inverse().get(1, 1).value,
            0.6, tol=1e-6
        )
    ))
    ts.run("inverse_singular_raises_BoundaryEvent", lambda: (
        _assert_raises(core.BoundaryEvent, lambda: M.from_values([[2.0, 4.0], [1.0, 2.0]]).inverse())
    ))
    ts.run("transpose", lambda: (
        _assert_close(
            M.from_values([[1.0, 2.0], [3.0, 4.0]]).transpose().get(1, 2).value, 3.0
        )
    ))
    ts.run("matrix_multiply_2x2", lambda: (
        _check_matrix_multiply_2x2(M)
    ))
    return ts


def _check_matrix_multiply_2x2(M) -> None:
    a = M.from_values([[1.0, 2.0], [3.0, 4.0]])
    b = M.from_values([[5.0, 6.0], [7.0, 8.0]])
    c = a.multiply(b)
    # [[1*5+2*7, 1*6+2*8], [3*5+4*7, 3*6+4*8]] = [[19, 22], [43, 50]]
    _assert_close(c.get(1, 1).value, 19.0)
    _assert_close(c.get(1, 2).value, 22.0)
    _assert_close(c.get(2, 1).value, 43.0)
    _assert_close(c.get(2, 2).value, 50.0)


def suite_keddeh_vector(core) -> TestSuite:
    ts = TestSuite("KeddehVector — unit tests")
    V = core.KeddehVector

    ts.run("from_floats", lambda: (
        _assert_equal(V.from_floats(1.0, 2.0, 3.0).dimension(), 3)
    ))
    ts.run("magnitude", lambda: (
        _assert_close(V.from_floats(3.0, 4.0).magnitude(), 5.0)
    ))
    ts.run("dot_product", lambda: (
        _assert_close(V.from_floats(1.0, 2.0, 3.0).dot(V.from_floats(4.0, 5.0, 6.0)), 32.0)
    ))
    ts.run("invert", lambda: (
        _assert_close(V.from_floats(1.0, -2.0, 3.0).invert().components[0].value, -1.0)
    ))
    ts.run("add_no_boundary", lambda: (
        _assert_close(V.from_floats(1.0, 2.0).add(V.from_floats(3.0, 4.0)).components[0].value, 4.0)
    ))
    ts.run("add_boundary_raises", lambda: (
        _assert_raises(core.BoundaryEvent, lambda: V.from_floats(1.0, 2.0).add(V.from_floats(-1.0, 3.0)))
    ))
    return ts


def suite_proofs(core) -> TestSuite:
    ts = TestSuite("Mathematical proofs — unit tests")

    ts.run("proof_neg_times_neg_positive", lambda: (
        _assert_true(core.proof_negative_times_negative(-3.0, -4.0)["product"] > 0)
    ))
    ts.run("proof_additive_inversion_is_boundary", lambda: (
        _assert_true("boundary_event" in core.proof_additive_inversion(7.0))
    ))
    ts.run("proof_division_transform_no_div_by_zero", lambda: (
        _assert_close(core.proof_division_transform(9.0, 3.0)["result"], 3.0)
    ))
    return ts


def suite_cartesian_comparison(cart) -> TestSuite:
    ts = TestSuite("CartesianMatrix comparison — unit tests")
    M = cart.CartesianMatrix

    ts.run("cartesian_zero_entry_allowed", lambda: (
        _assert_equal(M.from_values([[0.0, 1.0], [1.0, 0.0]]).get(0, 0), 0.0)
    ))
    ts.run("cartesian_singular_inverse_none", lambda: (
        _assert_true(M.from_values([[2.0, 4.0], [1.0, 2.0]]).inverse() is None)
    ))
    ts.run("cartesian_determinant_2x2", lambda: (
        _assert_close(M.from_values([[3.0, 8.0], [4.0, 6.0]]).determinant(), -14.0)
    ))
    ts.run("cartesian_transpose", lambda: (
        _assert_close(M.from_values([[1.0, 2.0], [3.0, 4.0]]).transpose().data[0][1], 3.0)
    ))

    ts.run("comparison_harness_division_by_zero", lambda: (
        _assert_true(
            not cart.ComparisonHarness().compare_division_by_zero().agrees
        )
    ))
    ts.run("comparison_harness_problems_list_length", lambda: (
        _assert_true(len(cart.ComparisonHarness().problems_keddeh_solves()) >= 3)
    ))
    return ts


def suite_physical_calibration(phys) -> TestSuite:
    ts = TestSuite("Physical calibration — unit tests")

    ts.run("temperature_boundary_proof", lambda: _check_temp_boundary(phys))
    ts.run("temperature_non_zero_results", lambda: _check_temp_non_zero(phys))
    ts.run("voltage_all_non_zero", lambda: _check_voltage_non_zero(phys))
    ts.run("motion_observer_at_own_boundary", lambda: _check_motion_boundary(phys))
    ts.run("quantum_superposition_boundary_event", lambda: _check_quantum(phys))
    return ts


def _check_temp_boundary(phys) -> None:
    results = phys.TemperatureCalibrationTest().run()
    proof = next(r for r in results if "proof" in r)
    assert proof["zero_passed_through"] is False


def _check_temp_non_zero(phys) -> None:
    results = phys.TemperatureCalibrationTest().run()
    data_rows = [r for r in results if "celsius" in r]
    for row in data_rows:
        assert row["celsius"] != 0.0


def _check_voltage_non_zero(phys) -> None:
    results = phys.VoltageCalibrationTest().run()
    data_rows = [r for r in results if "volts" in r]
    for row in data_rows:
        assert row["volts"] != 0.0


def _check_motion_boundary(phys) -> None:
    results = phys.MotionCalibrationTest().run()
    proof = next(r for r in results if "proof" in r)
    assert proof["train_sees_itself_at"] == 0.0
    assert proof["car_sees_itself_at"] == 0.0


def _check_quantum(phys) -> None:
    results = phys.QuantumCalibrationTest().run()
    superpos = next(r for r in results if r.get("test") == "superposition_boundary_event")
    assert "boundary_event" in superpos


def suite_geometric_transformations(geom) -> TestSuite:
    ts = TestSuite("Geometric transformations — unit tests")
    import math

    ts.run("rotation_2d_det_is_1", lambda: _check_rotation_det(geom, 45.0))
    ts.run("rotation_3d_det_is_1", lambda: _check_rotation_3d_det(geom, 45.0))
    ts.run("dimensional_collapse_cartesian", lambda: _check_cartesian_collapse(geom))
    ts.run("dimensional_collapse_keddeh_prevented", lambda: _check_keddeh_no_collapse(geom))
    ts.run("vector_scaling_no_origin_binding", lambda: _check_vector_scaling(geom))
    return ts


def _check_rotation_det(geom, deg) -> None:
    import math
    m = geom.rotation_2d_cartesian(math.radians(deg))
    _assert_close(m.determinant(), 1.0, tol=1e-6)


def _check_rotation_3d_det(geom, deg) -> None:
    import math
    m = geom.rotation_3d_x_cartesian(math.radians(deg))
    _assert_close(m.determinant(), 1.0, tol=1e-6)


def _check_cartesian_collapse(geom) -> None:
    from cartesian_comparison import CartesianMatrix
    cm = CartesianMatrix.from_values([[1.0, 0.0], [0.0, 0.0]])
    _assert_equal(cm.determinant(), 0.0)


def _check_keddeh_no_collapse(geom) -> None:
    from keddeh_matrix_core import KeddehMatrix, BoundaryEvent
    try:
        KeddehMatrix.from_values([[1.0, 0.0], [0.0, 0.0]])
        raise AssertionError("Expected ValueError for zero entry")
    except ValueError:
        pass   # correct — zero entry prevented


def _check_vector_scaling(geom) -> None:
    from keddeh_matrix_core import KeddehVector, KeddehValue
    v = KeddehVector.from_floats(2.0, 3.0)
    scaled = v.scale(KeddehValue(2.0))
    _assert_close(scaled.components[0].value, 4.0)
    _assert_close(scaled.components[1].value, 6.0)


def suite_virtualised_memory(vmem) -> TestSuite:
    ts = TestSuite("VIRTUALISED_MEMORY — unit tests")

    ts.run("set_and_get_1based", lambda: _check_vmem_set_get(vmem))
    ts.run("zero_index_raises", lambda: _check_vmem_zero_index(vmem))
    ts.run("negative_index_raises", lambda: _check_vmem_negative_index(vmem))
    ts.run("matrix_roundtrip_pass", lambda: (
        _assert_equal(vmem.VirtualisedMemoryIntegrationTest().run_matrix_roundtrip()["status"], "PASS")
    ))
    ts.run("active_state_count", lambda: _check_active_state(vmem))
    ts.run("deactivate_removes_cell", lambda: _check_deactivate(vmem))
    return ts


def _check_vmem_set_get(vmem) -> None:
    mem = vmem.VirtualisedMemory()
    mem.set(1, 1, 5.0)
    kv = mem.get(1, 1)
    assert kv is not None
    _assert_close(kv.value, 5.0)


def _check_vmem_zero_index(vmem) -> None:
    mem = vmem.VirtualisedMemory()
    mem.set(1, 1, 1.0)
    _assert_raises(vmem.ObserverBoundaryAccess, lambda: mem.get(0, 1))


def _check_vmem_negative_index(vmem) -> None:
    mem = vmem.VirtualisedMemory()
    _assert_raises(vmem.ObserverBoundaryAccess, lambda: mem.set(-1, 1, 1.0))


def _check_active_state(vmem) -> None:
    mem = vmem.VirtualisedMemory()
    mgr = vmem.ActiveStateManager(mem)
    mgr.activate(1, 1, 10.0)
    mgr.activate(2, 2, -5.0)
    _assert_equal(mgr.state_count(), 2)


def _check_deactivate(vmem) -> None:
    mem = vmem.VirtualisedMemory()
    mgr = vmem.ActiveStateManager(mem)
    mgr.activate(1, 1, 10.0)
    mgr.activate(1, 2, -3.0)
    mgr.deactivate(1, 1)
    _assert_equal(mgr.state_count(), 1)
    cells = mgr.active_cells()
    _assert_equal(cells[0].row, 1)
    _assert_equal(cells[0].col, 2)


# ---------------------------------------------------------------------------
# Performance benchmark
# ---------------------------------------------------------------------------

def run_benchmarks(core, cart) -> None:
    print("\n" + "=" * 60)
    print("Performance Benchmarks")
    print("=" * 60)

    harness = cart.ComparisonHarness()
    for size in [2, 4, 8]:
        result = harness.benchmark_matrix_multiply(size=size, iterations=500)
        print(f"  {size}x{size} multiply (500 iter): "
              f"Cartesian={result['cartesian_ms']}ms  "
              f"Keddeh={result['keddeh_ms']}ms  "
              f"ratio={result['ratio']}x  "
              f"boundary_events={result['keddeh_boundary_events']}")


# ---------------------------------------------------------------------------
# Assertion helpers
# ---------------------------------------------------------------------------

def _assert_raises(exc_type, fn: Callable) -> None:
    try:
        fn()
    except exc_type:
        return
    raise AssertionError(f"Expected {exc_type.__name__} but no exception was raised.")


def _assert_equal(a, b) -> None:
    assert a == b, f"Expected {b!r}, got {a!r}"


def _assert_close(a: float, b: float, tol: float = 1e-9) -> None:
    import math
    # Allow nan comparison only if both nan
    if math.isnan(a) and math.isnan(b):
        return
    assert abs(a - b) <= tol, f"Expected {b} ± {tol}, got {a}"


def _assert_true(condition: bool) -> None:
    assert condition, "Assertion failed"


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

def main() -> int:
    try:
        core, cart, phys, geom, vmem = _import_all()
    except ImportError as e:
        print(f"Import error: {e}")
        return 1

    suites = [
        suite_keddeh_value(core),
        suite_keddeh_arithmetic(core),
        suite_keddeh_matrix(core),
        suite_keddeh_vector(core),
        suite_proofs(core),
        suite_cartesian_comparison(cart),
        suite_physical_calibration(phys),
        suite_geometric_transformations(geom),
        suite_virtualised_memory(vmem),
    ]

    total_failures = 0
    for suite in suites:
        total_failures += suite.print_report()

    run_benchmarks(core, cart)

    print("\n" + "=" * 60)
    if total_failures == 0:
        print(f"ALL TESTS PASSED ({sum(len(s.results) for s in suites)} tests)")
    else:
        print(f"FAILURES: {total_failures} test(s) failed")
    print("Status: MODEL-LOCAL")
    print("=" * 60)

    return 0 if total_failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
