from __future__ import annotations
from dataclasses import asdict, dataclass
from hashlib import sha256
import json

from .coordinate_directory import DistributedCoordinateDirectory
from .layer2_reconciler import DesiredManifestation, Layer2Reconciler
from .tot_safety import ToTSafetyKernel
from observer2_runtime.kex_symbolic_bridge import BinaryBoundaryAdapter, SymbolicEnvelope

def _hash(value) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()

@dataclass(frozen=True)
class BoundaryCommitReceipt:
    semantic_root: str
    envelope_root: str
    wire_root: str
    directory_root: str
    committed_root: str
    manifestation_id: str
    endpoint: str
    generation: int
    receipt_hash: str

class KEXBoundaryIntegration:
    """Bind a verified symbolic KEX envelope to Report-03 commit/directory/L2 state.

    This adapter does not reinterpret IL-LLM meaning. It commits the already-bound
    semantic/envelope identities, materialises bytes only through BinaryBoundaryAdapter,
    and exposes the resulting carrier as desired Layer-2 state.
    """

    def __init__(self, kernel: ToTSafetyKernel, directory: DistributedCoordinateDirectory):
        self.kernel = kernel
        self.directory = directory

    def _commit(self, actor: str, command: str, payload: dict, voters: tuple[str, ...]):
        t = self.kernel.propose(actor=actor, command=command, payload=payload)
        votes = [self.kernel.vote(v, t) for v in voters]
        r = self.kernel.commit(t, votes)
        self.directory.apply(t, r)
        return t, r

    def commit_envelope(self, envelope: SymbolicEnvelope, *, actor: str, voters: tuple[str, ...],
                        coordinate: str, manifestation_id: str, endpoint: str, generation: int = 1):
        if coordinate not in self.directory.records:
            self._commit(actor, "DIRECTORY_REGISTER", {"coordinate": coordinate}, voters)

        wire = BinaryBoundaryAdapter.emit(envelope)
        wire_root = sha256(wire).hexdigest()
        payload = {
            "coordinate": coordinate,
            "manifestation_id": manifestation_id,
            "endpoint": endpoint,
            "generation": generation,
            "state": "ATTACHED",
            "semantic_root": envelope.semantic_root,
            "envelope_root": envelope.envelope_root,
            "wire_root": wire_root,
        }
        _, commit = self._commit(actor, "DIRECTORY_UPSERT_MANIFESTATION", payload, voters)
        body = {
            "semantic_root": envelope.semantic_root,
            "envelope_root": envelope.envelope_root,
            "wire_root": wire_root,
            "directory_root": self.directory.directory_root(),
            "committed_root": commit.committed_root,
            "manifestation_id": manifestation_id,
            "endpoint": endpoint,
            "generation": generation,
        }
        return wire, BoundaryCommitReceipt(**body, receipt_hash=_hash(body))

    @staticmethod
    def desired(receipt: BoundaryCommitReceipt) -> dict[str, DesiredManifestation]:
        return {receipt.manifestation_id: DesiredManifestation(
            receipt.manifestation_id, receipt.endpoint, receipt.generation, "ATTACHED"
        )}

    @staticmethod
    def reconcile(receipt: BoundaryCommitReceipt, observed: dict, actuator):
        return Layer2Reconciler().reconcile_once(KEXBoundaryIntegration.desired(receipt), observed, actuator)
