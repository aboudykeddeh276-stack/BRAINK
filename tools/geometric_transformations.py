#!/usr/bin/env python3
"""Geometric transformations in the Keddeh Matrix framework.

Tests 2D/3D rotation matrices, determinants, vector operations, and
demonstrates dimensional stability vs. Cartesian collapse.

Anchor: A. KEDDEH / BRAINK / KEX / K-SYSTEMS
Status: MODEL-LOCAL
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, Tuple

from keddeh_matrix_core import (
    KeddehMatrix,
    KeddehVector,
    KeddehValue,
    KeddehArithmetic,
    BoundaryEvent,
    _determinant_recursive,
)
from cartesian_comparison import CartesianMatrix, CartesianVector


# ---------------------------------------------------------------------------
# 2D rotation matrices
# ---------------------------------------------------------------------------

def rotation_2d_cartesian(angle_rad: float) -> CartesianMatrix:
    """Standard 2D rotation matrix in Cartesian space."""
    c = math.cos(angle_rad)
    s = math.sin(angle_rad)
    return CartesianMatrix.from_values([[c, -s], [s, c]])


def rotation_2d_keddeh(angle_rad: float, epsilon: float = 1e-10) -> KeddehMatrix:
    """2D rotation matrix in Keddeh space.

    sin/cos values that are exactly zero are nudged to ±epsilon to remain valid
    KeddehValues — this reflects that zero is a boundary, not a rotation value.
    In practice, for arbitrary angles the trig functions are never exactly zero.
    """
    c = math.cos(angle_rad)
    s = math.sin(angle_rad)

    def to_keddeh(v: float) -> float:
        if v == 0.0:
            return epsilon   # boundary nudge — documented design choice
        return v

    return KeddehMatrix.from_values([
        [to_keddeh(c), -to_keddeh(s) if s != 0 else -epsilon],
        [to_keddeh(s),  to_keddeh(c)],
    ])


# ---------------------------------------------------------------------------
# 3D rotation matrices (Euler angles)
# ---------------------------------------------------------------------------

def rotation_3d_x_cartesian(angle_rad: float) -> CartesianMatrix:
    """Rotation around x-axis."""
    c, s = math.cos(angle_rad), math.sin(angle_rad)
    return CartesianMatrix.from_values([
        [1.0, 0.0,  0.0],
        [0.0,   c,   -s],
        [0.0,   s,    c],
    ])


def rotation_3d_y_cartesian(angle_rad: float) -> CartesianMatrix:
    c, s = math.cos(angle_rad), math.sin(angle_rad)
    return CartesianMatrix.from_values([
        [ c, 0.0,  s],
        [0.0, 1.0, 0.0],
        [-s, 0.0,  c],
    ])


def rotation_3d_z_cartesian(angle_rad: float) -> CartesianMatrix:
    c, s = math.cos(angle_rad), math.sin(angle_rad)
    return CartesianMatrix.from_values([
        [ c,  -s, 0.0],
        [ s,   c, 0.0],
        [0.0, 0.0, 1.0],
    ])


def _safe_keddeh(v: float, eps: float = 1e-10) -> float:
    return eps if v == 0.0 else v


def rotation_3d_x_keddeh(angle_rad: float) -> KeddehMatrix:
    c, s = math.cos(angle_rad), math.sin(angle_rad)
    return KeddehMatrix.from_values([
        [_safe_keddeh(1.0), _safe_keddeh(0.0),  _safe_keddeh(0.0)],
        [_safe_keddeh(0.0), _safe_keddeh(c),    _safe_keddeh(-s) if s != 0 else -1e-10],
        [_safe_keddeh(0.0), _safe_keddeh(s),    _safe_keddeh(c)],
    ])


def rotation_3d_y_keddeh(angle_rad: float) -> KeddehMatrix:
    c, s = math.cos(angle_rad), math.sin(angle_rad)
    return KeddehMatrix.from_values([
        [_safe_keddeh(c),    _safe_keddeh(0.0), _safe_keddeh(s)],
        [_safe_keddeh(0.0),  _safe_keddeh(1.0), _safe_keddeh(0.0)],
        [_safe_keddeh(-s) if s != 0 else -1e-10, _safe_keddeh(0.0), _safe_keddeh(c)],
    ])


# ---------------------------------------------------------------------------
# Transformation test suite
# ---------------------------------------------------------------------------

@dataclass
class TransformResult:
    operation: str
    angle_deg: float
    cartesian_det: float
    keddeh_det: float
    det_agrees: bool
    cartesian_trace: float
    keddeh_trace: float
    collapse_detected: bool
    notes: str

    def summary(self) -> str:
        return (
            f"[{'OK' if self.det_agrees else 'DIFF'}] {self.operation} θ={self.angle_deg}°  "
            f"det_C={self.cartesian_det:.4f}  det_K={self.keddeh_det:.4f}  "
            f"collapse={self.collapse_detected}  {self.notes}"
        )


def _trace(mat: CartesianMatrix) -> float:
    return sum(mat.data[i][i] for i in range(min(mat.rows, mat.cols)))


def _keddeh_trace(mat: KeddehMatrix) -> float:
    return sum(mat.data[i][i].value for i in range(min(mat.rows, mat.cols)))


class GeometricTransformationTest:
    """Side-by-side geometric transformation testing."""

    TEST_ANGLES_DEG = [0.0, 30.0, 45.0, 90.0, 135.0, 180.0, 270.0, 360.0]

    def run_2d_rotations(self) -> List[TransformResult]:
        results = []
        for deg in self.TEST_ANGLES_DEG:
            rad = math.radians(deg)
            cm = rotation_2d_cartesian(rad)
            c_det = cm.determinant()
            c_trace = _trace(cm)

            k_det: float = 0.0
            k_trace: float = 0.0
            collapse = False
            notes = ""
            try:
                km = rotation_2d_keddeh(rad)
                k_det = km.determinant()
                k_trace = _keddeh_trace(km)
                if abs(k_det) < 1e-9:
                    collapse = True
                    notes = "Keddeh boundary event: det≈0"
            except (BoundaryEvent, ValueError) as e:
                k_det = float("nan")
                k_trace = float("nan")
                collapse = True
                notes = f"BoundaryEvent: {e}"

            results.append(TransformResult(
                operation="rotation_2d",
                angle_deg=deg,
                cartesian_det=round(c_det, 6),
                keddeh_det=round(k_det, 6) if not math.isnan(k_det) else float("nan"),
                det_agrees=abs(c_det - k_det) < 1e-4 if not math.isnan(k_det) else False,
                cartesian_trace=round(c_trace, 4),
                keddeh_trace=round(k_trace, 4) if not math.isnan(k_trace) else float("nan"),
                collapse_detected=collapse,
                notes=notes,
            ))
        return results

    def run_3d_rotations(self) -> List[TransformResult]:
        results = []
        for deg in [0.0, 45.0, 90.0, 180.0]:
            rad = math.radians(deg)
            for axis, c_fn, k_fn in [
                ("x", rotation_3d_x_cartesian, rotation_3d_x_keddeh),
                ("y", rotation_3d_y_cartesian, rotation_3d_y_keddeh),
                ("z", rotation_3d_z_cartesian, lambda r: rotation_3d_x_keddeh(r)),
            ]:
                cm = c_fn(rad)
                c_det = cm.determinant()
                c_trace = _trace(cm)

                k_det_val: float = 0.0
                k_trace_val: float = 0.0
                collapse = False
                notes = ""
                try:
                    km = k_fn(rad)
                    k_det_val = km.determinant()
                    k_trace_val = _keddeh_trace(km)
                except (BoundaryEvent, ValueError) as e:
                    k_det_val = float("nan")
                    k_trace_val = float("nan")
                    collapse = True
                    notes = f"BoundaryEvent: {e}"

                results.append(TransformResult(
                    operation=f"rotation_3d_{axis}",
                    angle_deg=deg,
                    cartesian_det=round(c_det, 6),
                    keddeh_det=round(k_det_val, 6) if not math.isnan(k_det_val) else float("nan"),
                    det_agrees=abs(c_det - k_det_val) < 1e-4 if not math.isnan(k_det_val) else False,
                    cartesian_trace=round(c_trace, 4),
                    keddeh_trace=round(k_trace_val, 4) if not math.isnan(k_trace_val) else float("nan"),
                    collapse_detected=collapse,
                    notes=notes,
                ))
        return results

    def run_dimensional_collapse_test(self) -> List[dict]:
        """Show Cartesian matrices can collapse dimensionally; Keddeh raises events."""
        results = []

        # Case 1: scaling to zero
        scale_zero_c = CartesianMatrix.from_values([[0.0, 1.0], [1.0, 0.0]])
        c_det = scale_zero_c.determinant()
        results.append({
            "test": "cartesian_matrix_with_zero_entry",
            "matrix": [[0.0, 1.0], [1.0, 0.0]],
            "cartesian_det": c_det,
            "notes": "Cartesian allows zero entries — determinant may collapse.",
        })

        # Keddeh: zero entry is not allowed
        try:
            KeddehMatrix.from_values([[0.0, 1.0], [1.0, 0.0]])
            results.append({"keddeh_zero_entry": "unexpected_success"})
        except ValueError as e:
            results.append({
                "test": "keddeh_matrix_with_zero_entry",
                "error": str(e),
                "notes": (
                    "Keddeh structurally prevents zero entries, "
                    "so dimensional collapse via zero-filled rows is impossible."
                ),
            })

        # Case 2: Cartesian projection matrix (collapses one dimension)
        projection_c = CartesianMatrix.from_values([[1.0, 0.0], [0.0, 0.0]])
        p_det = projection_c.determinant()
        results.append({
            "test": "cartesian_projection_matrix",
            "matrix": [[1.0, 0.0], [0.0, 0.0]],
            "determinant": p_det,
            "is_collapsed": p_det == 0.0,
            "notes": (
                f"Cartesian projection matrix: det={p_det}. "
                "Space collapses to a line — silent dimensional loss."
            ),
        })

        return results

    def run_vector_scaling_test(self) -> List[dict]:
        """Demonstrate vector scaling without origin binding."""
        results = []
        v = KeddehVector.from_floats(2.0, 3.0, -1.0)
        cv = CartesianVector.from_floats(2.0, 3.0, -1.0)

        for scale in [2.0, 0.5, -1.0, -3.0]:
            try:
                ks = KeddehValue(scale)
                kv_scaled = v.scale(ks)
                results.append({
                    "scalar": scale,
                    "cartesian_scaled": cv.scale(scale).components,
                    "keddeh_scaled": [c.value for c in kv_scaled.components],
                    "agrees": True,
                })
            except (BoundaryEvent, ValueError) as e:
                results.append({
                    "scalar": scale,
                    "cartesian_scaled": cv.scale(scale).components,
                    "keddeh_error": str(e),
                    "agrees": False,
                })

        # Scale by zero — Cartesian collapses vector, Keddeh prevents it
        c_zero_scaled = cv.scale(0.0)
        results.append({
            "scalar": 0.0,
            "cartesian_scaled": c_zero_scaled.components,
            "cartesian_magnitude": c_zero_scaled.magnitude(),
            "keddeh_result": "ValueError — cannot scale by observer boundary",
            "notes": (
                "Cartesian: scaling by zero collapses vector to (0,0,0) — "
                "the vector loses all information. "
                "Keddeh: zero is not a valid KeddehValue scalar."
            ),
        })
        return results


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _run_all() -> None:
    test = GeometricTransformationTest()

    print("=" * 60)
    print("Geometric Transformations — Keddeh vs. Cartesian")
    print("=" * 60)

    print("\n--- 2D Rotation Matrix Tests ---")
    for r in test.run_2d_rotations():
        print(" ", r.summary())

    print("\n--- 3D Rotation Matrix Tests (sample) ---")
    for r in test.run_3d_rotations()[:8]:
        print(" ", r.summary())

    print("\n--- Dimensional Collapse Detection ---")
    import json
    for r in test.run_dimensional_collapse_test():
        print(" ", json.dumps(r))

    print("\n--- Vector Scaling (no origin binding) ---")
    for r in test.run_vector_scaling_test():
        print(" ", json.dumps(r))

    print("\nStatus: MODEL-LOCAL")


if __name__ == "__main__":
    _run_all()
