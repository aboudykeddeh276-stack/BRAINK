from __future__ import annotations

from dataclasses import dataclass, asdict
from hashlib import sha256
import json
from typing import Any, Callable, Mapping

from .layer1_9_reconciler import Layer1to9Reconciler, LayerViolation, digest

@dataclass(frozen=True)
class KernelResult:
    run_id: str
    coordinate: str
    generation: int
    consensus_root: str
    directory_root: str
    layer9_root: str
    receipt_root: str
    evidence_root: str
    state: str

class FullSuiteKernel:
    """Composition kernel for ToT/directory/L1-9/L2/evidence boundaries.

    Adapters are injected. The kernel does not invent success for external effects.
    """

    def __init__(
        self,
        *,
        consensus_commit: Callable[[str, str, Mapping[str, Any]], Mapping[str, Any]],
        directory_apply: Callable[[str, int, Mapping[str, Any]], Mapping[str, Any]],
        execution_apply: Callable[[str, Mapping[str, Any], str], Mapping[str, Any]],
        observer_read: Callable[[str], Mapping[str, Any]],
        evidence_append: Callable[[str, Mapping[str, Any]], str],
    ) -> None:
        self.consensus_commit = consensus_commit
        self.directory_apply = directory_apply
        self.execution_apply = execution_apply
        self.observer_read = observer_read
        self.evidence_append = evidence_append
        self.layers = Layer1to9Reconciler()

    def execute(
        self,
        *,
        run_id: str,
        coordinate: str,
        generation: int,
        actor_id: str,
        authority_ref: str,
        payload: bytes,
        media_type: str,
        operation: str,
        target: str,
        route_id: str,
        geometry_mapping: str = "logical-coordinate",
        fault_layer: int | None = None,
    ) -> KernelResult:
        if not payload:
            raise LayerViolation("EMPTY_INGRESS_PAYLOAD")
        if str(coordinate).strip().upper() in {"0", "ZERO"}:
            raise LayerViolation("COORDINATE_ZERO_REJECTED")

        payload_hash = sha256(payload).hexdigest()
        consensus = dict(self.consensus_commit(
            actor_id,
            "COORDINATE_UPSERT",
            {"coordinate": coordinate, "generation": generation, "payload_hash": payload_hash, "target": target},
        ))
        for key in ("epoch", "index", "commit_root", "quorum_size", "membership_hash", "certificate_hash", "receipt_hash"):
            if key not in consensus:
                raise LayerViolation(f"CONSENSUS_ADAPTER_MISSING:{key}")

        directory = dict(self.directory_apply(
            coordinate,
            generation,
            {"payload_hash": payload_hash, "commit_root": consensus["commit_root"]},
        ))
        for key in ("directory_root", "coordinate_generation"):
            if key not in directory:
                raise LayerViolation(f"DIRECTORY_ADAPTER_MISSING:{key}")

        before = dict(self.observer_read(target))
        before_root = digest(before)

        idempotency_key = digest({
            "run_id": run_id,
            "coordinate": coordinate,
            "generation": generation,
            "operation": operation,
            "target": target,
            "payload_hash": payload_hash,
        })
        execution = dict(self.execution_apply(
            operation,
            {"coordinate": coordinate, "payload_hash": payload_hash, "generation": generation, "target": target},
            idempotency_key,
        ))
        if "result_root" not in execution:
            raise LayerViolation("EXECUTION_ADAPTER_MISSING:result_root")

        after = dict(self.observer_read(target))
        after_root = digest(after)
        changed = before_root != after_root

        geometry_root = digest({"mapping": geometry_mapping, "origin": "Singularity:1", "coordinate": coordinate})
        provisional_evidence = digest({
            "run_id": run_id,
            "coordinate": coordinate,
            "generation": generation,
            "payload_hash": payload_hash,
            "consensus_root": consensus["commit_root"],
            "directory_root": directory["directory_root"],
            "execution_root": execution["result_root"],
            "observation_root": after_root,
        })

        payloads = {
            1: {"payload_hash": payload_hash, "payload_bytes": len(payload), "media_type": media_type},
            2: {"actor_id": actor_id, "authority_ref": authority_ref, "capability": operation},
            3: {"coordinate": coordinate, "directory_root": directory["directory_root"], "coordinate_generation": directory["coordinate_generation"]},
            4: {"mapping": geometry_mapping, "origin": "Singularity:1", "geometry_root": geometry_root},
            5: {"route_id": route_id, "signal_type": operation, "destination": target},
            6: {"epoch": consensus["epoch"], "index": consensus["index"], "commit_root": consensus["commit_root"], "quorum_size": consensus["quorum_size"], "membership_hash": consensus["membership_hash"], "certificate_hash": consensus["certificate_hash"], "receipt_hash": consensus["receipt_hash"]},
            7: {"operation": operation, "target": target, "result_root": execution["result_root"]},
            8: {"observer_id": f"observer:{target}", "before_root": before_root, "after_root": after_root, "changed": changed},
            9: {"evidence_root": provisional_evidence, "receipt_count": 8, "claim_state": "OBSERVED"},
        }
        receipts = self.layers.reconcile_all(
            run_id=run_id,
            generation=generation,
            payloads=payloads,
            fault_layer=fault_layer,
        )
        bundle = self.layers.receipt_bundle()
        evidence_root = self.evidence_append("LAYER1_9_COMMIT", bundle)
        if not evidence_root:
            raise LayerViolation("EVIDENCE_APPEND_FAILED")

        return KernelResult(
            run_id=run_id,
            coordinate=coordinate,
            generation=generation,
            consensus_root=str(consensus["commit_root"]),
            directory_root=str(directory["directory_root"]),
            layer9_root=receipts[-1].output_root,
            receipt_root=receipts[-1].receipt_hash,
            evidence_root=str(evidence_root),
            state="COMMITTED",
        )


class ResidentBRAINKAdapters:
    """Adapter binding the current resident ToT, directory, L2 and evidence journal."""

    def __init__(self, members, evidence_path, actuator):
        from .tot_safety import ToTSafetyKernel
        from .coordinate_directory import DistributedCoordinateDirectory
        from .layer2_reconciler import Layer2Reconciler
        from .evidence_journal import EvidenceJournal
        self.members = tuple(members)
        self.tot = ToTSafetyKernel(self.members)
        self.directory = DistributedCoordinateDirectory(self.members)
        self.l2 = Layer2Reconciler()
        self.journal = EvidenceJournal(evidence_path)
        self.actuator = actuator
        self.observed = {}
        self._pending = None
        self._target_by_coordinate = {}

    def consensus(self, actor_id, command, payload):
        coordinate = payload["coordinate"]
        generation = int(payload["generation"])
        target = payload["target"]
        self._target_by_coordinate[coordinate] = target
        pending = []
        voters = self.members[: self.tot.quorum]
        if coordinate not in self.directory.records:
            register = self.tot.propose(
                actor=actor_id,
                command="DIRECTORY_REGISTER",
                payload={"coordinate": coordinate},
            )
            register_receipt = self.tot.commit(
                register, [self.tot.vote(v, register) for v in voters]
            )
            pending.append((register, register_receipt))
        upsert = self.tot.propose(
            actor=actor_id,
            command="DIRECTORY_UPSERT_MANIFESTATION",
            payload={
                "coordinate": coordinate,
                "manifestation_id": f"kernel:{coordinate}",
                "endpoint": target,
                "generation": generation,
                "state": "ATTACHED",
            },
        )
        upsert_receipt = self.tot.commit(
            upsert, [self.tot.vote(v, upsert) for v in voters]
        )
        pending.append((upsert, upsert_receipt))
        self._pending = pending
        qc = upsert_receipt.quorum_certificate
        return {
            "epoch": upsert.epoch,
            "index": upsert.index,
            "commit_root": upsert_receipt.committed_root,
            "quorum_size": self.tot.quorum,
            "membership_hash": upsert_receipt.membership_hash,
            "certificate_hash": qc.certificate_hash,
            "receipt_hash": upsert_receipt.receipt_hash,
        }

    def directory_apply(self, coordinate, generation, payload):
        if self._pending is None:
            raise LayerViolation("DIRECTORY_WITHOUT_PENDING_COMMIT")
        for t, receipt in self._pending:
            if t.payload.get("coordinate") != coordinate:
                raise LayerViolation("DIRECTORY_PENDING_COORDINATE_MISMATCH")
            self.directory.apply(t, receipt)
        self._pending = None
        return {
            "directory_root": self.directory.directory_root(),
            "coordinate_generation": self.directory.records[coordinate].generation,
        }

    def execute(self, operation, payload, idempotency_key):
        from .layer2_reconciler import DesiredManifestation
        coordinate = payload["coordinate"]
        target = payload["target"]
        generation = int(payload["generation"])
        manifestation_id = f"kernel:{coordinate}"
        desired = {manifestation_id: DesiredManifestation(manifestation_id, target, generation)}
        self.observed, receipt = self.l2.reconcile_once(desired, self.observed, self.actuator)
        if not receipt.converged:
            raise LayerViolation(f"L2_NOT_CONVERGED:{receipt.status}")
        return {"result_root": receipt.receipt_hash}

    def observe(self, target):
        values = {
            mid: {
                "manifestation_id": obs.manifestation_id,
                "endpoint": obs.endpoint,
                "generation": obs.generation,
                "state": obs.state,
            }
            for mid, obs in sorted(self.observed.items())
            if obs.endpoint == target
        }
        return values

    def evidence(self, kind, bundle):
        return self.journal.append(kind, dict(bundle)).record_hash

    def kernel(self):
        return FullSuiteKernel(
            consensus_commit=self.consensus,
            directory_apply=self.directory_apply,
            execution_apply=self.execute,
            observer_read=self.observe,
            evidence_append=self.evidence,
        )
