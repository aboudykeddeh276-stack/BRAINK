from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable, Sequence
import hashlib
import math

TAU = 2.0 * math.pi
SCHEMA = "braink.waveform-geometry.r40/v1"


def canonical_json(value: Any) -> str:
    import json
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def root(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


class GeometryValidationError(RuntimeError):
    pass


class ABCodec:
    @staticmethod
    def encode(payload: bytes) -> str:
        return "".join("B" if (byte >> shift) & 1 else "A" for byte in payload for shift in range(7, -1, -1))

    @staticmethod
    def decode(tokens: str) -> bytes:
        if not isinstance(tokens, str):
            raise TypeError("AB_TOKENS_MUST_BE_STRING")
        if len(tokens) % 8:
            raise ValueError("AB_TOKEN_LENGTH_NOT_BYTE_ALIGNED")
        if any(ch not in {"A", "B"} for ch in tokens):
            raise ValueError("AB_TOKEN_INVALID_SYMBOL")
        out = bytearray()
        for offset in range(0, len(tokens), 8):
            value = 0
            for ch in tokens[offset:offset + 8]:
                value = (value << 1) | (1 if ch == "B" else 0)
            out.append(value)
        return bytes(out)


@dataclass(frozen=True)
class GeometryConfig:
    major_radius: float = 10.0
    minor_radius: float = 3.0
    base_frequency: float = 432.0
    curvature_gain: float = 0.10

    def validate(self) -> None:
        values = (self.major_radius, self.minor_radius, self.base_frequency, self.curvature_gain)
        if not all(math.isfinite(v) for v in values):
            raise ValueError("GEOMETRY_CONFIG_NONFINITE")
        if self.major_radius <= self.minor_radius or self.minor_radius <= 0.0:
            raise ValueError("GEOMETRY_RADII_REQUIRE_R_GT_r_GT_0")
        if self.base_frequency <= 0.0:
            raise ValueError("GEOMETRY_BASE_FREQUENCY_INVALID")
        if not (0.0 <= self.curvature_gain < 1.0):
            raise ValueError("GEOMETRY_CURVATURE_GAIN_INVALID")

    @property
    def minimum_radial_magnitude(self) -> float:
        return self.major_radius - self.minor_radius

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


@dataclass(frozen=True)
class GeometrySample:
    index: int
    byte_value: int
    theta: float
    phi: float
    coordinate: tuple[float, float, float]
    radial_magnitude: float
    gaussian_curvature: float
    mean_curvature: float
    sample_root: str

    def semantic_body(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "byte_value": self.byte_value,
            "theta": self.theta,
            "phi": self.phi,
            "coordinate": list(self.coordinate),
            "radial_magnitude": self.radial_magnitude,
            "gaussian_curvature": self.gaussian_curvature,
            "mean_curvature": self.mean_curvature,
        }


@dataclass(frozen=True)
class ModulatedSample:
    index: int
    amplitude: float
    phase: float
    frequency: float
    gaussian_curvature: float
    geometry_sample_root: str

    def semantic_body(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GeometryFrame:
    schema: str
    config: dict[str, float]
    payload_sha256: str
    ab_token_sha256: str
    sample_count: int
    geometry_root: str
    modulation_root: str
    samples: tuple[ModulatedSample, ...]

    def semantic_body(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "config": self.config,
            "payload_sha256": self.payload_sha256,
            "ab_token_sha256": self.ab_token_sha256,
            "sample_count": self.sample_count,
            "geometry_root": self.geometry_root,
            "modulation_root": self.modulation_root,
            "samples": [s.semantic_body() for s in self.samples],
        }

    @property
    def frame_root(self) -> str:
        return root(self.semantic_body())


class WaveformGeometryEngine:
    def __init__(self, config: GeometryConfig | None = None):
        self.config = config or GeometryConfig()
        self.config.validate()

    @staticmethod
    def phase_for_byte(byte_value: int) -> float:
        if not 0 <= int(byte_value) <= 255:
            raise ValueError("BYTE_OUT_OF_RANGE")
        # Bin centres avoid the original 0 / 2*pi endpoint alias.
        return TAU * ((int(byte_value) + 0.5) / 256.0)

    @staticmethod
    def byte_for_phase(phase: float) -> int:
        if not math.isfinite(phase):
            raise GeometryValidationError("PHASE_NONFINITE")
        wrapped = phase % TAU
        return max(0, min(255, int(math.floor((wrapped / TAU) * 256.0))))

    def generate_geometry(self, payload: bytes) -> list[GeometrySample]:
        payload = bytes(payload)
        if not payload:
            return []
        R, r, n = self.config.major_radius, self.config.minor_radius, len(payload)
        out: list[GeometrySample] = []
        for i, byte in enumerate(payload):
            theta = TAU * ((i + 0.5) / n)
            phi = self.phase_for_byte(byte)
            cp, sp = math.cos(phi), math.sin(phi)
            ring = R + r * cp
            x = ring * math.cos(theta)
            y = ring * math.sin(theta)
            z = r * sp
            magnitude = math.sqrt(x*x + y*y + z*z)
            gaussian = cp / (r * ring)
            mean = -(R + 2.0*r*cp) / (2.0*r*ring)
            body = {
                "index": i, "byte_value": int(byte), "theta": theta, "phi": phi,
                "coordinate": [x, y, z], "radial_magnitude": magnitude,
                "gaussian_curvature": gaussian, "mean_curvature": mean,
            }
            out.append(GeometrySample(
                i, int(byte), theta, phi, (x, y, z), magnitude, gaussian, mean, root(body)
            ))
        return out

    def verify_geometry(self, payload: bytes, samples: Sequence[GeometrySample], tolerance: float = 1e-12) -> dict[str, Any]:
        expected = self.generate_geometry(payload)
        if len(expected) != len(samples):
            raise GeometryValidationError("GEOMETRY_SAMPLE_COUNT_MISMATCH")
        for actual, exp in zip(samples, expected):
            if actual.index != exp.index or actual.byte_value != exp.byte_value:
                raise GeometryValidationError("GEOMETRY_INDEX_OR_BYTE_MISMATCH")
            if actual.sample_root != exp.sample_root:
                raise GeometryValidationError("GEOMETRY_SAMPLE_ROOT_MISMATCH")
            for left, right in zip(actual.coordinate, exp.coordinate):
                if not math.isfinite(left) or abs(left-right) > tolerance:
                    raise GeometryValidationError("GEOMETRY_COORDINATE_DISTORTION")
            if abs(actual.radial_magnitude-exp.radial_magnitude) > tolerance:
                raise GeometryValidationError("GEOMETRY_MAGNITUDE_DISTORTION")
        minimum = min((s.radial_magnitude for s in samples), default=None)
        return {
            "status": "VERIFIED",
            "sample_count": len(samples),
            "minimum_radial_magnitude": minimum,
            "theoretical_lower_bound": self.config.minimum_radial_magnitude,
            "geometry_root": root([s.semantic_body() for s in samples]),
        }


class GeometricSignalModulator:
    def __init__(self, config: GeometryConfig | None = None):
        self.config = config or GeometryConfig()
        self.config.validate()

    def modulate(self, geometry: Sequence[GeometrySample]) -> list[ModulatedSample]:
        out = []
        r = self.config.minor_radius
        for sample in geometry:
            dimensionless_curvature = sample.gaussian_curvature * r * r
            frequency = self.config.base_frequency * (1.0 + self.config.curvature_gain * dimensionless_curvature)
            if frequency <= 0.0 or not math.isfinite(frequency):
                raise GeometryValidationError("MODULATION_FREQUENCY_INVALID")
            out.append(ModulatedSample(
                sample.index, sample.radial_magnitude, sample.phi, frequency,
                sample.gaussian_curvature, sample.sample_root,
            ))
        return out


class GeometricDemodulator:
    def __init__(self, config: GeometryConfig | None = None):
        self.config = config or GeometryConfig()
        self.config.validate()
        self.engine = WaveformGeometryEngine(self.config)
        self.modulator = GeometricSignalModulator(self.config)

    def demodulate(self, samples: Sequence[ModulatedSample]) -> bytes:
        values = list(samples)
        if any(sample.index != i for i, sample in enumerate(values)):
            raise GeometryValidationError("MODULATION_INDEX_SEQUENCE_INVALID")
        out = bytearray()
        for sample in values:
            for value in (sample.amplitude, sample.phase, sample.frequency, sample.gaussian_curvature):
                if not math.isfinite(value):
                    raise GeometryValidationError("MODULATION_NONFINITE")
            out.append(self.engine.byte_for_phase(sample.phase))
        return bytes(out)

    def verify_and_demodulate(
        self,
        frame: GeometryFrame,
        amplitude_tolerance: float = 1e-9,
        phase_tolerance: float = 1e-12,
        frequency_tolerance: float = 1e-9,
    ) -> tuple[bytes, dict[str, Any]]:
        if frame.schema != SCHEMA:
            raise GeometryValidationError("GEOMETRY_FRAME_SCHEMA_MISMATCH")
        if frame.sample_count != len(frame.samples):
            raise GeometryValidationError("GEOMETRY_FRAME_COUNT_MISMATCH")
        payload = self.demodulate(frame.samples)
        if hashlib.sha256(payload).hexdigest() != frame.payload_sha256:
            raise GeometryValidationError("GEOMETRY_PAYLOAD_HASH_MISMATCH")
        tokens = ABCodec.encode(payload)
        if hashlib.sha256(tokens.encode("ascii")).hexdigest() != frame.ab_token_sha256:
            raise GeometryValidationError("AB_TOKEN_HASH_MISMATCH")
        expected_geometry = self.engine.generate_geometry(payload)
        expected_modulation = self.modulator.modulate(expected_geometry)
        if root([s.semantic_body() for s in expected_geometry]) != frame.geometry_root:
            raise GeometryValidationError("GEOMETRY_ROOT_MISMATCH")
        if root([s.semantic_body() for s in frame.samples]) != frame.modulation_root:
            raise GeometryValidationError("MODULATION_ROOT_MISMATCH")
        for actual, exp in zip(frame.samples, expected_modulation):
            if actual.geometry_sample_root != exp.geometry_sample_root:
                raise GeometryValidationError("GEOMETRY_SAMPLE_COMMITMENT_MISMATCH")
            phase_error = abs((actual.phase-exp.phase+math.pi) % TAU - math.pi)
            if phase_error > phase_tolerance:
                raise GeometryValidationError("PHASE_DISTORTION")
            if abs(actual.amplitude-exp.amplitude) > amplitude_tolerance:
                raise GeometryValidationError("AMPLITUDE_DISTORTION")
            if abs(actual.frequency-exp.frequency) > frequency_tolerance:
                raise GeometryValidationError("FREQUENCY_DISTORTION")
        receipt = {
            "status": "VERIFIED",
            "payload_sha256": frame.payload_sha256,
            "sample_count": frame.sample_count,
            "minimum_radial_magnitude": min((s.amplitude for s in frame.samples), default=None),
            "theoretical_lower_bound": self.config.minimum_radial_magnitude,
            "geometry_root": frame.geometry_root,
            "modulation_root": frame.modulation_root,
            "frame_root": frame.frame_root,
        }
        receipt["receipt_root"] = root(receipt)
        return payload, receipt


class WaveformGeometryPipeline:
    def __init__(self, config: GeometryConfig | None = None):
        self.config = config or GeometryConfig()
        self.config.validate()
        self.engine = WaveformGeometryEngine(self.config)
        self.modulator = GeometricSignalModulator(self.config)
        self.demodulator = GeometricDemodulator(self.config)

    def encode(self, payload: bytes) -> GeometryFrame:
        payload = bytes(payload)
        tokens = ABCodec.encode(payload)
        geometry = self.engine.generate_geometry(payload)
        self.engine.verify_geometry(payload, geometry)
        modulation = self.modulator.modulate(geometry)
        return GeometryFrame(
            SCHEMA, self.config.to_dict(), hashlib.sha256(payload).hexdigest(),
            hashlib.sha256(tokens.encode("ascii")).hexdigest(), len(payload),
            root([s.semantic_body() for s in geometry]),
            root([s.semantic_body() for s in modulation]),
            tuple(modulation),
        )

    def decode(self, frame: GeometryFrame) -> tuple[bytes, dict[str, Any]]:
        return self.demodulator.verify_and_demodulate(frame)


def mutate_sample(sample: ModulatedSample, **changes: Any) -> ModulatedSample:
    body = asdict(sample)
    body.update(changes)
    return ModulatedSample(**body)


def frame_with_samples(frame: GeometryFrame, samples: Iterable[ModulatedSample], recompute_modulation_root: bool = False) -> GeometryFrame:
    values = tuple(samples)
    body = asdict(frame)
    body["samples"] = values
    if recompute_modulation_root:
        body["modulation_root"] = root([s.semantic_body() for s in values])
    return GeometryFrame(**body)


def geometry_observation_state_root(node_id: str, frame: GeometryFrame, receipt: dict[str, Any]) -> str:
    """Receiver proof projected as an observed state root for the resident Layer-2 reconciler."""
    return root({
        "node_id": node_id,
        "payload_sha256": frame.payload_sha256,
        "frame_root": frame.frame_root,
        "geometry_root": frame.geometry_root,
        "modulation_root": frame.modulation_root,
        "geometry_receipt_root": receipt["receipt_root"],
    })
