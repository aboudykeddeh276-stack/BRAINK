from __future__ import annotations

from typing import Any, Callable
from urllib.parse import quote
from urllib.request import Request, urlopen
import hashlib
import json

from runtime.R25.system_evolution_runtime import canonical_json


PROOF_RELAY_SCHEMA = "braink.fabric-proof-relay.r40/v1"


def proof_hash(body: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(body).encode("utf-8")).hexdigest()


def http_fetch_peer_proof(endpoint: str, challenge: str, *, token: str | None = None, timeout: float = 2.0,
                          max_response_bytes: int = 1024 * 1024) -> dict[str, Any]:
    if int(max_response_bytes) <= 0:
        raise ValueError("PROOF_RESPONSE_LIMIT_INVALID")
    url = str(endpoint).rstrip("/") + "/v1/fabric/proof?challenge=" + quote(str(challenge), safe="")
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + str(token)
    with urlopen(Request(url, method="GET", headers=headers), timeout=timeout) as response:
        if int(response.status) != 200:
            raise RuntimeError(f"PEER_PROOF_HTTP_STATUS:{response.status}")
        raw = response.read(int(max_response_bytes) + 1)
    if len(raw) > int(max_response_bytes):
        raise RuntimeError("PEER_PROOF_RESPONSE_TOO_LARGE")
    try:
        value = json.loads(raw.decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise RuntimeError("PEER_PROOF_UTF8_INVALID") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("PEER_PROOF_JSON_INVALID") from exc
    if not isinstance(value, dict):
        raise RuntimeError("PEER_PROOF_OBJECT_REQUIRED")
    return value


class FabricProofRelayR40:
    """Verify and persist proofs for already-admitted R38/R40 fabric peers.

    This is deliberately not called consensus. It performs challenge/readback,
    verifies the existing R38 proof construction, records local evidence, and
    reports state-root drift. It never auto-promotes a changed remote root and
    never mutates remote state.
    """

    def __init__(self, node):
        self.node = node

    def _admitted_peer(self, peer_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
        peer_id = str(peer_id)
        peers = self.node.peers()
        peer = peers.get(peer_id)
        if peer is None:
            raise ValueError("UNKNOWN_FABRIC_PEER:" + peer_id)
        admissions = self.node.computer.readback().get("memory", {}).get("fabric_admissions", {})
        admission = admissions.get(peer_id) if isinstance(admissions, dict) else None
        if not isinstance(admission, dict) or admission.get("acknowledged") is not True:
            raise ValueError("PEER_NOT_ADMITTED:" + peer_id)
        return peer, admission

    def challenge(self, peer_id: str) -> str:
        peer, _ = self._admitted_peer(peer_id)
        ident = self.node.identity()
        sequence = len(getattr(self.node.computer.ledger, "events", ()))
        material = {
            "schema": PROOF_RELAY_SCHEMA,
            "challenger_node_id": ident["node_id"],
            "challenger_constructor_id": ident["constructor_id"],
            "challenger_ledger_sequence": sequence,
            "peer_id": str(peer_id),
            "registered_peer_state_root": str(peer["state_root"]),
            "registered_peer_resident_root_set_digest": str(peer["resident_root_set_digest"]),
        }
        return "CHALLENGE-" + proof_hash(material)

    @staticmethod
    def _verify_raw(peer_id: str, peer: dict[str, Any], challenge: str, proof: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(proof, dict) or proof.get("status") != "PROVED":
            raise ValueError("PEER_PROOF_REQUIRED")
        body = proof.get("body")
        if not isinstance(body, dict):
            raise ValueError("PEER_PROOF_BODY_REQUIRED")
        if proof.get("proof") != proof_hash(body):
            raise ValueError("PEER_PROOF_HASH_INVALID")
        expected = {
            "node_id": str(peer_id),
            "challenge": str(challenge),
            "resident_root_set_digest": str(peer["resident_root_set_digest"]),
        }
        for key, expected_value in expected.items():
            if str(body.get(key)) != expected_value:
                raise ValueError(f"PEER_PROOF_MISMATCH:{key}")
        if not str(body.get("constructor_id", "")).strip():
            raise ValueError("PEER_PROOF_CONSTRUCTOR_REQUIRED")
        observed_root = str(body.get("state_root", ""))
        if not observed_root:
            raise ValueError("PEER_PROOF_STATE_ROOT_REQUIRED")
        registered_root = str(peer["state_root"])
        return {
            "registered_state_root": registered_root,
            "observed_state_root": observed_root,
            "root_match": observed_root == registered_root,
            "proof_root": str(proof["proof"]),
            "constructor_id": str(body["constructor_id"]),
        }

    def verify(self, peer_id: str, challenge: str, proof: dict[str, Any]) -> dict[str, Any]:
        peer, admission = self._admitted_peer(peer_id)
        checked = self._verify_raw(str(peer_id), peer, str(challenge), proof)
        sequence_before = len(getattr(self.node.computer.ledger, "events", ()))
        verification = "VERIFIED_STABLE_ROOT" if checked["root_match"] else "DRIFT:PEER_STATE_ROOT_CHANGED"
        receipt = {
            "schema": PROOF_RELAY_SCHEMA,
            "peer_id": str(peer_id),
            "challenge": str(challenge),
            "verification": verification,
            "registered_state_root": checked["registered_state_root"],
            "observed_state_root": checked["observed_state_root"],
            "resident_root_set_digest": str(peer["resident_root_set_digest"]),
            "proof_root": checked["proof_root"],
            "constructor_id": checked["constructor_id"],
            "authority": str(admission.get("authority", "")),
            "local_ledger_sequence_before_receipt": sequence_before,
            "remote_state_mutation": False,
            "peer_registration_mutation": False,
            "consensus_claim": False,
        }
        receipts = dict(self.node.computer.readback().get("memory", {}).get("fabric_peer_proof_receipts", {}))
        receipts[str(peer_id)] = receipt
        self.node.computer.write_memory("fabric_peer_proof_receipts", receipts)
        readback = self.node.computer.readback().get("memory", {}).get("fabric_peer_proof_receipts", {}).get(str(peer_id))
        if readback != receipt:
            raise RuntimeError("PEER_PROOF_RECEIPT_READBACK_FAILED")
        if not self.node.computer.ledger.verify():
            raise RuntimeError("PEER_PROOF_RECEIPT_LEDGER_FAILED")
        return {
            "status": verification,
            "peer_id": str(peer_id),
            "receipt": readback,
            "ledger_verified": True,
        }

    def fetch_and_verify(self, peer_id: str, *, token: str | None = None,
                         fetcher: Callable[..., dict[str, Any]] = http_fetch_peer_proof) -> dict[str, Any]:
        peer, _ = self._admitted_peer(peer_id)
        challenge = self.challenge(peer_id)
        proof = fetcher(str(peer["endpoint"]), challenge, token=token)
        return self.verify(peer_id, challenge, proof)

    def snapshot(self) -> dict[str, Any]:
        receipts = self.node.computer.readback().get("memory", {}).get("fabric_peer_proof_receipts", {})
        return {
            "schema": PROOF_RELAY_SCHEMA,
            "node_id": self.node.node_id,
            "peer_proofs": dict(receipts) if isinstance(receipts, dict) else {},
            "ledger_verified": self.node.computer.ledger.verify(),
            "consensus_claim": False,
        }
