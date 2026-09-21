from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import hashlib
import hmac
import json
import math
import random
import tempfile
import time

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


class Ledger:
    def __init__(self):
        self.rows = []

    def append(self, **kwargs):
        body = dict(kwargs)
        body["sequence"] = len(self.rows) + 1
        body["previous"] = self.rows[-1]["semantic_hash"] if self.rows else None
        body["semantic_hash"] = sha256_json(body)
        self.rows.append(body)
        return Packet(f"pkt_{len(self.rows):09d}", body["semantic_hash"])


SECRET = b"report03-waveform-ci"
AUTH = "authority://source/local"


def sign(p):
    return hmac.new(SECRET, canonical_json(p.semantic_body()).encode(), hashlib.sha256).hexdigest()


def verify(p):
    return hmac.compare_digest(sign(p), p.attestation)


def entry(node, coord, state, caps):
    return CoordinateEntry(
        node_id=node, coordinate=coord, generation=1, sequence=1,
        logical_identity=f"node://{node}", state_root=state, template_root="tpl-report03",
        network_endpoints=(f"local://{node.lower()}",), capabilities=caps,
        authority=AUTH, health="READY",
    )


def expect_error(fn, contains):
    try:
        fn()
    except Exception as exc:
        if contains not in str(exc):
            raise AssertionError(f"expected {contains}, got {type(exc).__name__}:{exc}")
        return type(exc).__name__ + ":" + str(exc)
    raise AssertionError("expected failure")


def main():
    results = []

    payload = bytes(range(256))
    tokens = ABCodec.encode(payload)
    assert ABCodec.decode(tokens) == payload
    results.append({"case": "AB_EXHAUSTIVE", "status": "PASS"})

    engine = WaveformGeometryEngine()
    legacy_equal = math.isclose(0.0 % (2*math.pi), (2*math.pi) % (2*math.pi), abs_tol=1e-15)
    zero, high = engine.generate_geometry(bytes([0,255]))
    assert legacy_equal and zero.phi != high.phi
    results.append({"case": "PHASE_ALIAS_FALSIFIER", "status": "PASS", "legacy_alias": True, "patched_alias": False})

    pipe = WaveformGeometryPipeline()
    recovered, receipt = pipe.decode(pipe.encode(payload))
    assert recovered == payload
    assert receipt["minimum_radial_magnitude"] >= 7.0 - 1e-12
    results.append({"case": "ALL_BYTES_ROUNDTRIP", "status": "PASS", "minimum_radial_magnitude": receipt["minimum_radial_magnitude"]})

    rng = random.Random(297)
    random_payload = bytes(rng.randrange(256) for _ in range(4096))
    assert pipe.decode(pipe.encode(random_payload))[0] == random_payload
    results.append({"case": "RANDOM_4096_ROUNDTRIP", "status": "PASS"})

    coords = engine.generate_geometry(payload)
    assert min(s.radial_magnitude for s in coords) >= 7.0 - 1e-12
    assert any(abs(component) < 0.1 for sample in coords for component in sample.coordinate)
    results.append({"case": "RADIAL_NOT_COORDINATE_ZERO_BOUNDARY", "status": "PASS"})

    distorted = engine.generate_geometry(b"BRAINK")
    first = distorted[0]
    distorted[0] = replace(first, coordinate=(first.coordinate[0]+0.25, first.coordinate[1], first.coordinate[2]))
    err = expect_error(lambda: engine.verify_geometry(b"BRAINK", distorted), "GEOMETRY_")
    results.append({"case": "COORDINATE_DISTORTION", "status": "PASS", "error": err})

    f = pipe.encode(b"signal")
    samples = list(f.samples)
    samples[0] = mutate_sample(samples[0], amplitude=samples[0].amplitude + 0.25)
    err = expect_error(lambda: pipe.decode(frame_with_samples(f, samples, True)), "AMPLITUDE_DISTORTION")
    results.append({"case": "AMPLITUDE_DISTORTION", "status": "PASS", "error": err})

    samples = list(f.samples)
    samples[1] = mutate_sample(samples[1], frequency=samples[1].frequency + 0.25)
    err = expect_error(lambda: pipe.decode(frame_with_samples(f, samples, True)), "FREQUENCY_DISTORTION")
    results.append({"case": "FREQUENCY_DISTORTION", "status": "PASS", "error": err})

    samples = list(f.samples)
    samples[0] = mutate_sample(samples[0], phase=samples[0].phase + (2*math.pi/256.0)*0.75)
    try:
        pipe.decode(frame_with_samples(f, samples, True))
    except GeometryValidationError as exc:
        assert "GEOMETRY_PAYLOAD_HASH_MISMATCH" in str(exc) or "PHASE_DISTORTION" in str(exc)
        results.append({"case": "PHASE_DISTORTION", "status": "PASS", "error": str(exc)})
    else:
        raise AssertionError("phase distortion accepted")

    with tempfile.TemporaryDirectory() as td:
        state = Path(td)
        ledger = Ledger()
        directory = DistributedCoordinateDirectory(state/"directory.json", ledger=ledger)
        kernel = ToTSafetyKernel(state/"tot.json", ledger=ledger, max_hops=4)
        reconciler = Layer2Reconciler(directory, kernel, ledger=ledger)
        assert directory.register(entry("A",(1,1),"root-A",("tot.propose",)))["status"] == "COMMITTED"
        desired = DesiredNodeState("B",(2,2),"node://B","tpl-report03",AUTH,("state.update",))
        initial = ObservedNodeState("B",(2,2),"node://B","pre-geometry","tpl-report03",("local://b",),("state.update",),AUTH,"READY",True)
        assert reconciler.reconcile(desired, initial, bootstrap_verifier=lambda _: True)["status"] == "REGISTERED"

        frame = pipe.encode(payload)
        recovered, geometry_receipt = pipe.decode(frame)
        assert recovered == payload
        state_root = geometry_observation_state_root("B", frame, geometry_receipt)
        observed = ObservedNodeState("B",(2,2),"node://B",state_root,"tpl-report03",("local://geometry",),("state.update",),AUTH,"READY",True)
        mutable = observed.mutable_projection()
        mutable["network_endpoints"] = sorted(set(mutable["network_endpoints"]))
        mutable["capabilities"] = sorted(set(mutable["capabilities"]))
        target = directory.resolve("B")
        draft = TransitionProposal("A","B",directory.resolve("A")["state_root"],target["entry_root"],1,"state.update",sha256_json(mutable),AUTH,("A",),"")
        proposal = TransitionProposal(**{**draft.__dict__, "attestation": sign(draft)})
        outcome = reconciler.reconcile(desired, observed, proposer_entry=directory.resolve("A"), proposal=proposal, authority_verifier=verify)
        assert outcome["status"] == "RECONCILED"
        assert directory.resolve("B")["state_root"] == state_root
        results.append({"case": "GEOMETRY_TOT_LAYER2", "status": "PASS", "state_root": state_root})

        # Corrupted geometry cannot create a new observed state, therefore cannot reach ToT.
        bad = list(frame.samples)
        bad[10] = mutate_sample(bad[10], phase=bad[10].phase + (2*math.pi/256.0)*0.75)
        before = directory.resolve("B")["entry_root"]
        try:
            pipe.decode(frame_with_samples(frame, bad, True))
        except GeometryValidationError:
            pass
        else:
            raise AssertionError("bad geometry accepted")
        assert directory.resolve("B")["entry_root"] == before
        results.append({"case": "BAD_GEOMETRY_NO_DIRECTORY_MUTATION", "status": "PASS"})

    benchmark_payload = hashlib.sha256(b"BRAINK-WAVEFORM-GEOMETRY").digest() * 8
    encode_ms=[]; decode_ms=[]
    for _ in range(100):
        t=time.perf_counter_ns(); bf=pipe.encode(benchmark_payload); encode_ms.append((time.perf_counter_ns()-t)/1e6)
        t=time.perf_counter_ns(); pipe.decode(bf); decode_ms.append((time.perf_counter_ns()-t)/1e6)

    def percentile(xs,p):
        values=sorted(xs); return values[min(len(values)-1, max(0, math.ceil(p*len(values))-1))]

    report = {
        "schema": "braink.report03.waveform-geometry-ci/v1",
        "status": "PASS",
        "checks": results,
        "check_count": len(results),
        "benchmark": {
            "payload_bytes": len(benchmark_payload),
            "iterations": 100,
            "encode_ms": {"median": sorted(encode_ms)[len(encode_ms)//2], "p95": percentile(encode_ms,.95), "p99": percentile(encode_ms,.99), "max": max(encode_ms)},
            "decode_ms": {"median": sorted(decode_ms)[len(decode_ms)//2], "p95": percentile(decode_ms,.95), "p99": percentile(decode_ms,.99), "max": max(decode_ms)},
        },
        "claim_boundaries": {
            "analog_transmission": "NOT_PROVEN",
            "physical_jitter_mitigation": "NOT_PROVEN",
            "zero_free_tensor": "NOT_PROVEN",
            "radial_magnitude_lower_bound": "PROVEN_FOR_R_GT_r",
            "wasm_boundary": "NOT_IMPLEMENTED_IN_THIS_MODULE",
            "multi_host_transport": "NOT_EXECUTED",
        },
    }
    report["receipt_root"] = sha256_json(report)
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
