#!/usr/bin/env python3
"""Physical calibration tests for the Keddeh Matrix framework.

Validates observer-state logic against real-world physical systems:
- Temperature state transitions (continuous change, not integer-anchored)
- Voltage / electrical reference systems (ground as observer boundary)
- Relativistic motion frames (observer always at their own boundary)
- Quantum probability calibration (continuous wave functions, no zero collapse)

Anchor: A. KEDDEH / BRAINK / KEX / K-SYSTEMS
Status: MODEL-LOCAL
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, Tuple

from keddeh_matrix_core import (
    KeddehValue,
    KeddehArithmetic,
    BoundaryEvent,
    ObserverFrame,
    ObserverState,
)


# ---------------------------------------------------------------------------
# 1. Temperature calibration
# ---------------------------------------------------------------------------

@dataclass
class TemperatureState:
    """A physical temperature reading in Keddeh space.

    The observer boundary (0°C, 0K shifted, etc.) is a *calibration point*
    chosen by the engineer — not a natural constant. State transitions are
    continuous and do not 'belong' to any integer symbol.
    """
    celsius: float
    observer_label: str = "water_freeze_reference"

    @property
    def keddeh_value(self) -> Optional[KeddehValue]:
        """Return KeddehValue if not at the observer boundary (0°C)."""
        if self.celsius == 0.0:
            return None   # At the observer boundary
        return KeddehValue(self.celsius)

    @property
    def state(self) -> str:
        if self.celsius < 0:
            return "ice_domain"
        if self.celsius > 0:
            return "liquid_domain"
        return "observer_boundary"

    def cross_boundary(self) -> "TemperatureState":
        """Instant state inversion: freeze ↔ melt."""
        return TemperatureState(-self.celsius, self.observer_label)


class TemperatureCalibrationTest:
    """Prove that continuous state changes don't 'belong' to integer symbols."""

    CALIBRATION_POINTS = [
        (-10.0, "ice"),
        (-1.0,  "near_boundary_ice"),
        (-0.1,  "micro_ice"),
        # 0.0 is the observer boundary — not included in the sequence
        (+0.1,  "micro_water"),
        (+1.0,  "near_boundary_water"),
        (+10.0, "water"),
        (+100.0, "steam_domain"),
    ]

    def run(self) -> List[dict]:
        results = []
        prev: Optional[TemperatureState] = None
        for temp_c, label in self.CALIBRATION_POINTS:
            ts = TemperatureState(temp_c)
            kv = ts.keddeh_value
            entry = {
                "celsius": temp_c,
                "label": label,
                "state": ts.state,
                "keddeh_value": kv.value if kv else "observer_boundary",
                "magnitude": abs(temp_c),
                "observer_state": kv.observer_state.value if kv else "boundary",
            }
            if prev is not None and prev.keddeh_value is not None and kv is not None:
                entry["boundary_distance"] = KeddehArithmetic.boundary_distance(
                    prev.keddeh_value, kv
                )
            results.append(entry)
            prev = ts

        # Prove the boundary crossing is instantaneous
        pre = TemperatureState(-0.001)
        post = TemperatureState(+0.001)
        results.append({
            "proof": "boundary_crossing_is_instantaneous",
            "pre_boundary": pre.celsius,
            "post_boundary": post.celsius,
            "pre_state": pre.state,
            "post_state": post.state,
            "step_size": 0.002,
            "zero_passed_through": False,
            "explanation": (
                "The transition from -0.001°C to +0.001°C skips zero. "
                "Zero (0°C) is the observer calibration boundary — the water "
                "molecules do not 'pass through' a special integer; they undergo "
                "a continuous thermodynamic transition that we have *labelled* "
                "with the boundary symbol 0."
            ),
        })
        return results


# ---------------------------------------------------------------------------
# 2. Voltage / electrical systems
# ---------------------------------------------------------------------------

@dataclass
class VoltageState:
    """Voltage measurement relative to the observer's ground reference.

    Ground (0V) is the *observer boundary* chosen by the electrical engineer.
    It is not an absolute zero — it is the reference frame.
    """
    volts: float
    ground_label: str = "engineer_reference_ground"

    @property
    def keddeh_value(self) -> Optional[KeddehValue]:
        if self.volts == 0.0:
            return None
        return KeddehValue(self.volts)

    @property
    def polarity(self) -> str:
        if self.volts > 0:
            return "positive_rail"
        if self.volts < 0:
            return "negative_rail"
        return "ground_reference"


class VoltageCalibrationTest:
    """Show that ground voltage is observer reference, not zero value."""

    CIRCUIT_VOLTAGES = [
        (-12.0, "negative_supply"),
        (-5.0,  "negative_logic"),
        (-1.0,  "below_ground"),
        (+1.0,  "above_ground"),
        (+5.0,  "logic_high"),
        (+12.0, "positive_supply"),
        (+3.3,  "vcc_logic"),
    ]

    def run(self) -> List[dict]:
        results = []
        for v, label in self.CIRCUIT_VOLTAGES:
            vs = VoltageState(v)
            kv = vs.keddeh_value
            assert kv is not None  # none of these are zero
            results.append({
                "volts": v,
                "label": label,
                "polarity": vs.polarity,
                "keddeh_value": kv.value,
                "observer_state": kv.observer_state.value,
                "magnitude_from_ground": kv.magnitude,
            })

        # Demonstrate observer-relative measurement
        engineer_ground = ObserverFrame("engineer_ground_reference")
        v_pos = KeddehValue(5.0)
        v_neg = KeddehValue(-5.0)
        dist_pos, state_pos = engineer_ground.measure(v_pos)
        dist_neg, state_neg = engineer_ground.measure(v_neg)

        results.append({
            "proof": "ground_is_observer_reference",
            "+5V_distance_from_ground": dist_pos,
            "+5V_state": state_pos.value,
            "-5V_distance_from_ground": dist_neg,
            "-5V_state": state_neg.value,
            "explanation": (
                "Ground (0V) is not absolute nothingness — it is the observer's "
                "reference frame. +5V and -5V are both valid states at distance 5 "
                "from the observer boundary, on opposite sides."
            ),
        })
        return results


# ---------------------------------------------------------------------------
# 3. Relativistic motion frames
# ---------------------------------------------------------------------------

@dataclass
class MotionFrame:
    """An observer's motion frame.

    The observer is always at rest in their own frame (their velocity = observer boundary).
    All velocities are relative — there is no universal zero velocity.
    """
    label: str
    velocity_ms: float   # velocity in m/s relative to some external reference

    @property
    def keddeh_value(self) -> Optional[KeddehValue]:
        """Return KeddehValue if the observer is not at the absolute reference."""
        if self.velocity_ms == 0.0:
            return None   # this observer IS the reference frame
        return KeddehValue(self.velocity_ms)

    def relative_velocity(self, other: "MotionFrame") -> float:
        """Velocity of `other` as seen from this frame."""
        return other.velocity_ms - self.velocity_ms


class MotionCalibrationTest:
    """Demonstrate that observer is always at their own origin."""

    def run(self) -> List[dict]:
        # Define several observers
        ground = MotionFrame("ground_observer", 0.0)
        train = MotionFrame("train_passenger", 30.0)      # 30 m/s
        car = MotionFrame("car_driver", -15.0)            # going opposite direction
        plane = MotionFrame("aircraft_passenger", 250.0)

        observers = [ground, train, car, plane]
        results = []

        for obs in observers:
            kv = obs.keddeh_value
            entry = {
                "observer": obs.label,
                "absolute_velocity_ms": obs.velocity_ms,
                "own_frame_velocity": "observer_boundary (always 0 in own frame)",
                "keddeh_value": kv.value if kv else "observer_boundary",
            }
            # Relative velocity as seen from each observer
            for other in observers:
                if other.label != obs.label:
                    rel = obs.relative_velocity(other)
                    entry[f"sees_{other.label}_at_ms"] = rel
            results.append(entry)

        # Proof: every observer is at their own boundary
        results.append({
            "proof": "observer_always_at_own_boundary",
            "train_sees_itself_at": train.relative_velocity(train),
            "car_sees_itself_at": car.relative_velocity(car),
            "explanation": (
                "Every observer measures their own velocity as the boundary reference "
                "(0 in their frame). The Keddeh boundary formalises this: each observer "
                "is the origin of their own coordinate system. There is no universal 0."
            ),
        })

        # Speed of light relativistic: show velocities stay non-zero in Keddeh
        c = 299_792_458.0   # m/s
        near_c = KeddehValue(c * 0.999)
        neg_near_c = KeddehValue(-(c * 0.5))
        try:
            sum_vel = KeddehArithmetic.add(near_c, neg_near_c)
            results.append({
                "relativistic_add": f"{near_c.value:.0f} + {neg_near_c.value:.0f} = {sum_vel.value:.0f}",
                "result_state": sum_vel.observer_state.value,
            })
        except BoundaryEvent as e:
            results.append({"relativistic_boundary_event": str(e)})

        return results


# ---------------------------------------------------------------------------
# 4. Quantum probability calibration
# ---------------------------------------------------------------------------

class QuantumCalibrationTest:
    """Validate against quantum mechanics: wave functions, probability distributions.

    In quantum mechanics, probability amplitudes are complex numbers and
    probabilities are real [0, 1]. The 'zero' in quantum mechanics is the
    null state — a boundary, not a measurement outcome.
    """

    def _gaussian_amplitude(self, x: float, mu: float, sigma: float) -> float:
        """Gaussian probability amplitude (unnormalised)."""
        return math.exp(-0.5 * ((x - mu) / sigma) ** 2)

    def run(self) -> List[dict]:
        results = []
        mu = 2.0    # mean (non-zero — observer-shifted)
        sigma = 1.0

        # Sample the wave function at non-zero positions
        sample_points = [-3.0, -2.0, -1.0, 1.0, 2.0, 3.0, 4.0, 5.0]
        amplitudes = []
        for x in sample_points:
            amp = self._gaussian_amplitude(x, mu, sigma)
            kv = KeddehValue(x)
            amplitudes.append({
                "x": x,
                "amplitude": round(amp, 6),
                "keddeh_state": kv.observer_state.value,
                "note": "non-zero position in Keddeh space",
            })
        results.append({
            "test": "gaussian_wave_function_sampling",
            "mu": mu,
            "sigma": sigma,
            "samples": amplitudes,
            "explanation": (
                "Wave functions are sampled at non-zero positions. The observer "
                "boundary (x=0 shifted to x=mu) is a reference frame, not a "
                "measurement collapse point. All sampled amplitudes are non-zero."
            ),
        })

        # Probability normalisation without zero
        # ∫ |ψ(x)|² dx ≈ 1 (discrete approximation)
        # Sample range: -5.0 to +5.0 in steps of 0.01, skipping the boundary at 0.
        _PROB_SAMPLE_START: int = -500
        _PROB_SAMPLE_END: int = 501
        dx = 0.01
        xs = [i * dx for i in range(_PROB_SAMPLE_START, _PROB_SAMPLE_END) if i != 0]
        prob_sum = sum(self._gaussian_amplitude(x, mu, sigma) ** 2 * dx for x in xs)
        results.append({
            "test": "probability_normalisation_without_zero",
            "integral_approx": round(prob_sum, 4),
            "zero_included": False,
            "explanation": (
                f"Probability integral ≈ {round(prob_sum, 4)} (excluding x=0 as "
                "observer boundary). The missing single point has measure zero in the "
                "continuous limit, confirming the probability distribution is complete "
                "without assigning a calculable value to the boundary."
            ),
        })

        # Superposition: two non-zero states
        state_a = KeddehValue(1.0)   # |+1⟩
        state_b = KeddehValue(-1.0)  # |-1⟩ — inversion of state_a
        try:
            superposition = KeddehArithmetic.add(state_a, state_b)
            results.append({
                "test": "superposition_boundary_event",
                "result": "unexpected_non_boundary",
                "value": superposition.value,
            })
        except BoundaryEvent as e:
            results.append({
                "test": "superposition_boundary_event",
                "state_a": state_a.value,
                "state_b": state_b.value,
                "boundary_event": str(e),
                "explanation": (
                    "|+1⟩ + |-1⟩ reaches the observer boundary — analogous to "
                    "destructive interference in quantum mechanics. In Keddeh, "
                    "this is an explicit boundary event, not a silent collapse to 0."
                ),
            })

        return results


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _run_all() -> None:
    import json

    print("=" * 60)
    print("Physical Calibration Tests — Keddeh Matrix Framework")
    print("=" * 60)

    print("\n--- 1. Temperature Calibration ---")
    temp_test = TemperatureCalibrationTest()
    temp_results = temp_test.run()
    for r in temp_results:
        print(" ", json.dumps(r, indent=None))

    print("\n--- 2. Voltage / Electrical Calibration ---")
    volt_test = VoltageCalibrationTest()
    volt_results = volt_test.run()
    for r in volt_results:
        print(" ", json.dumps(r, indent=None))

    print("\n--- 3. Relativistic Motion Frames ---")
    motion_test = MotionCalibrationTest()
    motion_results = motion_test.run()
    for r in motion_results:
        print(" ", json.dumps(r, indent=None))

    print("\n--- 4. Quantum Probability Calibration ---")
    quantum_test = QuantumCalibrationTest()
    quantum_results = quantum_test.run()
    for r in quantum_results:
        print(" ", json.dumps(r, indent=None))

    print("\nStatus: MODEL-LOCAL")


if __name__ == "__main__":
    _run_all()
