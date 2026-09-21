from __future__ import annotations

from dataclasses import replace
import hashlib
import hmac
import math
import random

import pytest

from enterprise.report03_engineering_r40 import (
    CoordinateEntry, DesiredNodeState, DistributedCoordinateDirectory, Layer2Reconciler,
    ObservedNodeState, ToTSafetyKernel, TransitionProposal, canonical_json, sha256_json,
)
from enterprise.waveform_geometry_r40 import (
    ABCodec, GeometryConfig, GeometryValidationError, WaveformGeometryEngine,
    WaveformGeometryPipeline, frame_with_samples, geometry_observation_state_root,
    mutate_sample,
)


class Packet:
    def __init__(self, packet_id, semantic_hash):
        self.packet_id = packet_id
        self.semantic_hash = semantic_hash


class TestLedger:
    def __init__(self):
        self.rows = []

    def append(self, **kwargs):
        body = dict(kwargs)
        body["sequence"] = len(self.rows) + 1
        body["previous"] = self.rows[-1]["semantic_hash"] if self.rows else None
        body["semantic_hash"] = sha256_json(body)
        self.rows.append(body)
        return Packet(f"pkt_{len(self.rows):09d}", body["semantic_hash"])


SECRET = b"report03-waveform-geometry"
AUTH = "authority://source/local"


def sign(p):
    return hmac.new(SECRET, canonical_json(p.semantic_body()).encode(), hashlib.sha256).hexdigest()


def verify(p):
    return hmac.compare_digest(sign(p), p.attestation)


def entry(node, coord, state, caps, template="tpl-report03"):
    return CoordinateEntry(
        node_id=node, coordinate=coord, generation=1, sequence=1,
        logical_identity=f"node://{node}", state_root=state, template_root=template,
        network_endpoints=(f"local://{node.lower()}",), capabilities=caps,
        authority=AUTH, health="READY",
    )


def test_ab_codec_exhaustive_roundtrip():
    payload = bytes(range(256))
    tokens = ABCodec.encode(payload)
    assert len(tokens) == 2048
    assert ABCodec.decode(tokens) == payload


def test_ab_codec_rejects_invalid_input():
    with pytest.raises(ValueError, match="AB_TOKEN_INVALID_SYMBOL"):
        ABCodec.decode("AAAAAAAX")
    with pytest.raises(ValueError, match="AB_TOKEN_LENGTH_NOT_BYTE_ALIGNED"):
        ABCodec.decode("A")


def test_original_zero_and_255_phase_mapping_aliases_but_fixed_mapping_does_not():
    legacy_0 = 0.0
    legacy_255 = 2.0 * math.pi
    assert math.isclose(legacy_0 % (2*math.pi), legacy_255 % (2*math.pi), abs_tol=1e-15)
    engine = WaveformGeometryEngine()
    a, b = engine.generate_geometry(bytes([0, 255]))
    assert not math.isclose(a.phi, b.phi, abs_tol=1e-15)
    assert engine.byte_for_phase(a.phi) == 0
    assert engine.byte_for_phase(b.phi) == 255


def test_all_byte_values_roundtrip():
    pipe = WaveformGeometryPipeline()
    payload = bytes(range(256))
    recovered, receipt = pipe.decode(pipe.encode(payload))
    assert recovered == payload
    assert receipt["status"] == "VERIFIED"


def test_random_payload_roundtrip():
    rng = random.Random(297)
    payload = bytes(rng.randrange(256) for _ in range(4096))
    pipe = WaveformGeometryPipeline()
    recovered, _ = pipe.decode(pipe.encode(payload))
    assert recovered == payload


def test_torus_only_guarantees_nonzero_radial_magnitude():
    config = GeometryConfig(10.0, 3.0)
    engine = WaveformGeometryEngine(config)
    samples = engine.generate_geometry(bytes(range(256)))
    assert min(s.radial_magnitude for s in samples) >= 7.0 - 1e-12
    assert any(abs(component) < 0.1 for s in samples for component in s.coordinate)


def test_invalid_radii_are_rejected():
    with pytest.raises(ValueError, match="GEOMETRY_RADII_REQUIRE"):
        GeometryConfig(3.0, 3.0).validate()
    with pytest.raises(ValueError, match="GEOMETRY_RADII_REQUIRE"):
        GeometryConfig(2.0, 3.0).validate()


def test_coordinate_distortion_is_detected():
    engine = WaveformGeometryEngine()
    payload = b"BRAINK"
    samples = engine.generate_geometry(payload)
    first = samples[0]
    samples[0] = replace(first, coordinate=(first.coordinate[0] + 0.25, first.coordinate[1], first.coordinate[2]))
    with pytest.raises(GeometryValidationError):
        engine.verify_geometry(payload, samples)


def test_amplitude_distortion_is_detected():
    pipe = WaveformGeometryPipeline()
    frame = pipe.encode(b"wave")
    samples = list(frame.samples)
    samples[1] = mutate_sample(samples[1], amplitude=samples[1].amplitude + 0.01)
    with pytest.raises(GeometryValidationError, match="AMPLITUDE_DISTORTION"):
        pipe.decode(frame_with_samples(frame, samples, True))


def test_frequency_distortion_is_detected():
    pipe = WaveformGeometryPipeline()
    frame = pipe.encode(b"wave")
    samples = list(frame.samples)
    samples[2] = mutate_sample(samples[2], frequency=samples[2].frequency + 0.01)
    with pytest.raises(GeometryValidationError, match="FREQUENCY_DISTORTION"):
        pipe.decode(frame_with_samples(frame, samples, True))


def test_phase_distortion_cannot_promote_wrong_payload():
    pipe = WaveformGeometryPipeline()
    frame = pipe.encode(b"wave")
    samples = list(frame.samples)
    samples[0] = mutate_sample(samples[0], phase=samples[0].phase + (2*math.pi/256.0)*0.60)
    with pytest.raises(GeometryValidationError, match="GEOMETRY_PAYLOAD_HASH_MISMATCH|PHASE_DISTORTION"):
        pipe.decode(frame_with_samples(frame, samples, True))


def test_reorder_and_nonfinite_are_rejected():
    pipe = WaveformGeometryPipeline()
    frame = pipe.encode(b"AB")
    with pytest.raises(GeometryValidationError, match="MODULATION_INDEX_SEQUENCE_INVALID"):
        pipe.decode(frame_with_samples(frame, reversed(frame.samples), True))
    samples = list(frame.samples)
    samples[0] = mutate_sample(samples[0], amplitude=float("nan"))
    with pytest.raises(GeometryValidationError, match="MODULATION_NONFINITE"):
        pipe.decode(frame_with_samples(frame, samples, True))


def test_empty_payload_is_valid():
    pipe = WaveformGeometryPipeline()
    recovered, receipt = pipe.decode(pipe.encode(b""))
    assert recovered == b""
    assert receipt["sample_count"] == 0


def test_frame_metadata_tamper_is_detected():
    pipe = WaveformGeometryPipeline()
    frame = pipe.encode(b"geometry")
    with pytest.raises(GeometryValidationError, match="GEOMETRY_PAYLOAD_HASH_MISMATCH"):
        pipe.decode(replace(frame, payload_sha256="00"*32))


def test_verified_geometry_state_can_only_enter_directory_through_tot_layer2(tmp_path):
    ledger = TestLedger()
    directory = DistributedCoordinateDirectory(tmp_path/"directory.json", ledger=ledger)
    kernel = ToTSafetyKernel(tmp_path/"tot.json", ledger=ledger, max_hops=4)
    reconciler = Layer2Reconciler(directory, kernel, ledger=ledger)

    directory.register(entry("A", (1,1), "root-A", ("tot.propose",)))
    desired = DesiredNodeState("B", (2,2), "node://B", "tpl-report03", AUTH, ("state.update",))
    initial = ObservedNodeState("B", (2,2), "node://B", "pre-geometry", "tpl-report03", ("local://b",), ("state.update",), AUTH, "READY", True)
    assert reconciler.reconcile(desired, initial, bootstrap_verifier=lambda _: True)["status"] == "REGISTERED"

    pipe = WaveformGeometryPipeline()
    frame = pipe.encode(bytes(range(256)))
    payload, receipt = pipe.decode(frame)
    assert payload == bytes(range(256))
    geometry_state = geometry_observation_state_root("B", frame, receipt)
    observed = ObservedNodeState("B", (2,2), "node://B", geometry_state, "tpl-report03", ("local://geometry",), ("state.update",), AUTH, "READY", True)

    mutable = observed.mutable_projection()
    mutable["network_endpoints"] = sorted(set(mutable["network_endpoints"]))
    mutable["capabilities"] = sorted(set(mutable["capabilities"]))
    target = directory.resolve("B")
    draft = TransitionProposal("A", "B", directory.resolve("A")["state_root"], target["entry_root"], 1, "state.update", sha256_json(mutable), AUTH, ("A",), "")
    proposal = TransitionProposal(**{**draft.__dict__, "attestation": sign(draft)})
    out = reconciler.reconcile(desired, observed, proposer_entry=directory.resolve("A"), proposal=proposal, authority_verifier=verify)
    assert out["status"] == "RECONCILED"
    assert directory.resolve("B")["state_root"] == geometry_state
