from __future__ import annotations

import hashlib
import hmac
import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from enterprise.report03_engineering_r40 import (
    CoordinateEntry,
    DesiredNodeState,
    DistributedCoordinateDirectory,
    Layer2Reconciler,
    ObservedNodeState,
    ToTSafetyKernel,
    TransitionProposal,
    canonical_json,
    sha256_json,
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

    def verify(self):
        previous = None
        for index, row in enumerate(self.rows, 1):
            candidate = dict(row)
            claimed = candidate.pop("semantic_hash")
            if candidate["sequence"] != index or candidate["previous"] != previous:
                return False
            if sha256_json(candidate) != claimed:
                return False
            previous = claimed
        return True


SECRET = b"report03-r40-test"
AUTH = "authority://source/local"


def entry(node, coord, state="s1", caps=("tot.propose", "state.update"), template="tpl"):
    return CoordinateEntry(
        node_id=node,
        coordinate=tuple(coord),
        generation=1,
        sequence=1,
        logical_identity=f"node://{node}",
        state_root=state,
        template_root=template,
        network_endpoints=(f"local://{node.lower()}",),
        capabilities=tuple(sorted(caps)),
        authority=AUTH,
        health="READY",
    )


def sign(proposal):
    return hmac.new(SECRET, canonical_json(proposal.semantic_body()).encode(), hashlib.sha256).hexdigest()


def verify(proposal):
    return hmac.compare_digest(sign(proposal), proposal.attestation)


def proposal(source, target, seq=1, source_state="s1", payload="payload"):
    draft = TransitionProposal(
        source, target["node_id"], source_state, target["entry_root"], seq,
        "state.update", payload, AUTH, (source,), ""
    )
    return TransitionProposal(**{**draft.__dict__, "attestation": sign(draft)})


@pytest.fixture
def layer(tmp_path):
    ledger = TestLedger()
    directory = DistributedCoordinateDirectory(tmp_path / "directory.json", ledger=ledger)
    kernel = ToTSafetyKernel(tmp_path / "tot.json", ledger=ledger, max_hops=4)
    return ledger, directory, kernel


def test_coordinate_collision_allows_one_owner(layer):
    _, directory, _ = layer

    def register(node):
        return directory.register(entry(node, (2, 2)))["status"]

    with ThreadPoolExecutor(max_workers=8) as pool:
        statuses = list(pool.map(register, [f"N{i}" for i in range(16)]))

    assert statuses.count("COMMITTED") == 1
    assert statuses.count("BLOCKED:COORDINATE_OCCUPIED") == 15


def test_directory_stale_cas_is_rejected(layer):
    _, directory, _ = layer
    first = directory.register(entry("A", (1, 1)))["entry"]
    assert directory.update("A", expected_entry_root="stale", state_root="s2")["status"] == "BLOCKED:DIRECTORY_CAS_CONFLICT"
    assert directory.resolve("A")["entry_root"] == first["entry_root"]


def test_equal_sequence_divergence_is_fork(tmp_path):
    left_ledger = TestLedger()
    right_ledger = TestLedger()
    left = DistributedCoordinateDirectory(tmp_path / "left.json", ledger=left_ledger)
    right = DistributedCoordinateDirectory(tmp_path / "right.json", ledger=right_ledger)

    first = left.register(entry("A", (1, 1)))["entry"]
    assert right.merge_snapshot(left.snapshot())["status"] == "MERGED"

    assert left.update("A", expected_entry_root=first["entry_root"], state_root="left")["status"] == "COMMITTED"
    assert right.update("A", expected_entry_root=first["entry_root"], state_root="right")["status"] == "COMMITTED"

    merged = right.merge_snapshot(left.snapshot())
    assert merged["status"] == "CONFLICT"
    assert merged["conflicts"][0]["reason"] == "CONCURRENT_FORK_SAME_SEQUENCE"


def test_directory_tamper_fails_restart(layer, tmp_path):
    ledger, directory, _ = layer
    directory.register(entry("A", (1, 1)))
    path = tmp_path / "directory.json"
    body = json.loads(path.read_text())
    body["entries"]["A"]["health"] = "TAMPERED"
    path.write_text(json.dumps(body))

    with pytest.raises(RuntimeError, match="DIRECTORY_HEAD_MISMATCH|DIRECTORY_ENTRY_HASH_MISMATCH"):
        DistributedCoordinateDirectory(path, ledger=ledger)


def test_tot_authorizes_valid_proposal(layer):
    ledger, directory, kernel = layer
    directory.register(entry("A", (1, 1), caps=("tot.propose",)))
    target = directory.register(entry("B", (1, 2), caps=("state.update",)))["entry"]
    p = proposal("A", target)
    result = kernel.authorize(p, source_entry=directory.resolve("A"), target_entry=directory.resolve("B"), authority_verifier=verify)
    assert result["status"] == "AUTHORIZED"
    assert ledger.verify()


def test_tot_invalid_attestation_has_no_commit(layer):
    ledger, directory, kernel = layer
    directory.register(entry("A", (1, 1), caps=("tot.propose",)))
    target = directory.register(entry("B", (1, 2), caps=("state.update",)))["entry"]
    p = proposal("A", target)
    bad = TransitionProposal(**{**p.__dict__, "attestation": "00" * 32})
    before = kernel.snapshot()
    result = kernel.authorize(bad, source_entry=directory.resolve("A"), target_entry=directory.resolve("B"), authority_verifier=verify)
    assert result["status"] == "FAILED:TOT_ATTESTATION_INVALID"
    assert kernel.snapshot() == before


def test_tot_replay_is_blocked(layer):
    _, directory, kernel = layer
    directory.register(entry("A", (1, 1), caps=("tot.propose",)))
    target = directory.register(entry("B", (1, 2), caps=("state.update",)))["entry"]
    p = proposal("A", target)
    assert kernel.authorize(p, source_entry=directory.resolve("A"), target_entry=directory.resolve("B"), authority_verifier=verify)["status"] == "AUTHORIZED"
    p2 = proposal("A", target, seq=1, payload="different")
    assert kernel.authorize(p2, source_entry=directory.resolve("A"), target_entry=directory.resolve("B"), authority_verifier=verify)["status"] == "BLOCKED:TOT_REPLAY_OR_STALE_SEQUENCE"


def test_tot_cycle_and_hop_limit(layer):
    _, directory, kernel = layer
    directory.register(entry("A", (1, 1), caps=("tot.propose",)))
    target = directory.register(entry("B", (1, 2), caps=("state.update",)))["entry"]

    p = proposal("A", target)
    cyc = TransitionProposal(**{**p.__dict__, "hop_path": ("A", "C", "A")})
    assert kernel.authorize(cyc, source_entry=directory.resolve("A"), target_entry=directory.resolve("B"), authority_verifier=verify)["status"] == "BLOCKED:TOT_CYCLE_DETECTED"

    hop = TransitionProposal(**{**p.__dict__, "logical_sequence": 2, "hop_path": ("A", "C", "D", "E", "F")})
    assert kernel.authorize(hop, source_entry=directory.resolve("A"), target_entry=directory.resolve("B"), authority_verifier=verify)["status"] == "BLOCKED:TOT_HOP_LIMIT"


def desired():
    return DesiredNodeState("B", (2, 2), "node://B", "tplB", AUTH, ("state.update",))


def observed(state="s1", coord=(2, 2), template="tplB", endpoint="local://b"):
    return ObservedNodeState("B", coord, "node://B", state, template, (endpoint,), ("state.update",), AUTH, "READY", True)


def test_layer2_bootstrap_and_fixed_point(layer):
    ledger, directory, kernel = layer
    reconciler = Layer2Reconciler(directory, kernel, ledger=ledger)
    assert reconciler.reconcile(desired(), observed(), bootstrap_verifier=lambda _: True)["status"] == "REGISTERED"
    assert reconciler.reconcile(desired(), observed())["status"] == "FIXED_POINT"


def test_layer2_identity_drift_fails(layer):
    ledger, directory, kernel = layer
    reconciler = Layer2Reconciler(directory, kernel, ledger=ledger)
    result = reconciler.reconcile(desired(), observed(coord=(2, 3)), bootstrap_verifier=lambda _: True)
    assert result["status"] == "FAILED:IDENTITY_DRIFT"
    assert "COORDINATE" in result["fields"]


def test_layer2_mutable_drift_requires_tot(layer):
    ledger, directory, kernel = layer
    reconciler = Layer2Reconciler(directory, kernel, ledger=ledger)
    assert reconciler.reconcile(desired(), observed(), bootstrap_verifier=lambda _: True)["status"] == "REGISTERED"
    assert reconciler.reconcile(desired(), observed(state="s2"))["status"] == "BLOCKED:TOT_PROOF_REQUIRED"


def test_layer2_authorized_drift_reconciles(layer):
    ledger, directory, kernel = layer
    reconciler = Layer2Reconciler(directory, kernel, ledger=ledger)
    assert reconciler.reconcile(desired(), observed(), bootstrap_verifier=lambda _: True)["status"] == "REGISTERED"
    directory.register(entry("A", (1, 1), caps=("tot.propose",)))

    target = directory.resolve("B")
    obs = observed(state="s2", endpoint="local://b2")
    projection = obs.mutable_projection()
    projection["network_endpoints"] = sorted(set(projection["network_endpoints"]))
    projection["capabilities"] = sorted(set(projection["capabilities"]))
    p = proposal("A", target, payload=sha256_json(projection))

    result = reconciler.reconcile(
        desired(), obs,
        proposer_entry=directory.resolve("A"),
        proposal=p,
        authority_verifier=verify,
    )
    assert result["status"] == "RECONCILED"
    assert directory.resolve("B")["state_root"] == "s2"
