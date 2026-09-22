from __future__ import annotations

from dataclasses import dataclass, asdict
from hashlib import sha256
import json
from typing import Any, Callable, Mapping

class LayerViolation(RuntimeError):
    pass

def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")

def digest(value: Any) -> str:
    return sha256(canonical(value)).hexdigest()

@dataclass(frozen=True)
class LayerSpec:
    layer: int
    name: str
    required_fields: tuple[str, ...]

@dataclass(frozen=True)
class LayerReceipt:
    run_id: str
    layer: int
    name: str
    generation: int
    prior_receipt_hash: str
    input_root: str
    payload_root: str
    output_root: str
    status: str
    error: str | None
    receipt_hash: str

    @classmethod
    def build(
        cls,
        *,
        run_id: str,
        spec: LayerSpec,
        generation: int,
        prior_receipt_hash: str,
        input_root: str,
        payload_root: str,
        output_root: str,
        status: str,
        error: str | None,
    ) -> "LayerReceipt":
        body = {
            "run_id": run_id,
            "layer": spec.layer,
            "name": spec.name,
            "generation": generation,
            "prior_receipt_hash": prior_receipt_hash,
            "input_root": input_root,
            "payload_root": payload_root,
            "output_root": output_root,
            "status": status,
            "error": error,
        }
        return cls(receipt_hash=digest(body), **body)

class Layer1to9Reconciler:
    GENESIS = sha256(b"BRAINK-LAYER1-9-GENESIS-R2").hexdigest()

    SPECS = {
        1: LayerSpec(1, "INGRESS", ("payload_hash", "payload_bytes", "media_type")),
        2: LayerSpec(2, "IDENTITY", ("actor_id", "authority_ref", "capability")),
        3: LayerSpec(3, "COORDINATE", ("coordinate", "directory_root", "coordinate_generation")),
        4: LayerSpec(4, "GEOMETRY", ("mapping", "origin", "geometry_root")),
        5: LayerSpec(5, "PROPAGATION", ("route_id", "signal_type", "destination")),
        6: LayerSpec(6, "CONSENSUS", ("epoch", "index", "commit_root", "quorum_size", "membership_hash", "certificate_hash", "receipt_hash")),
        7: LayerSpec(7, "EXECUTION", ("operation", "target", "result_root")),
        8: LayerSpec(8, "OBSERVATION", ("observer_id", "before_root", "after_root", "changed")),
        9: LayerSpec(9, "EVIDENCE", ("evidence_root", "receipt_count", "claim_state")),
    }

    def __init__(self) -> None:
        self._committed: dict[int, LayerReceipt] = {}
        self._payloads: dict[int, Mapping[str, Any]] = {}
        self._failures: list[LayerReceipt] = []
        self._generation = 0
        self._run_id: str | None = None

    @property
    def state(self) -> dict[int, LayerReceipt]:
        return dict(self._committed)

    @property
    def failures(self) -> tuple[LayerReceipt, ...]:
        return tuple(self._failures)

    @property
    def root(self) -> str:
        if 9 not in self._committed:
            raise LayerViolation("PIPELINE_NOT_SEALED")
        return self._committed[9].output_root

    @property
    def receipt_root(self) -> str:
        if 9 not in self._committed:
            raise LayerViolation("PIPELINE_NOT_SEALED")
        return self._committed[9].receipt_hash

    def _validate_payload(self, spec: LayerSpec, payload: Mapping[str, Any]) -> None:
        missing = [field for field in spec.required_fields if field not in payload]
        if missing:
            raise LayerViolation(f"LAYER_{spec.layer}_MISSING_FIELDS:{','.join(missing)}")
        if spec.layer == 1:
            if int(payload["payload_bytes"]) < 0:
                raise LayerViolation("INGRESS_NEGATIVE_BYTE_COUNT")
            if len(str(payload["payload_hash"])) != 64:
                raise LayerViolation("INGRESS_HASH_INVALID")
        elif spec.layer == 2:
            if str(payload["actor_id"]).strip().upper() in {"0", "ZERO"}:
                raise LayerViolation("IDENTITY_ZERO_ACTOR_REJECTED")
            if not payload["authority_ref"]:
                raise LayerViolation("IDENTITY_AUTHORITY_REQUIRED")
        elif spec.layer == 3:
            if str(payload["coordinate"]).strip().upper() in {"0", "ZERO"}:
                raise LayerViolation("COORDINATE_ZERO_REJECTED")
            if int(payload["coordinate_generation"]) <= 0:
                raise LayerViolation("COORDINATE_GENERATION_INVALID")
        elif spec.layer == 6:
            if int(payload["epoch"]) <= 0 or int(payload["index"]) <= 0:
                raise LayerViolation("CONSENSUS_POSITION_INVALID")
            if int(payload["quorum_size"]) < 2:
                raise LayerViolation("CONSENSUS_QUORUM_INVALID")
            for field in ("commit_root", "membership_hash", "certificate_hash", "receipt_hash"):
                value = str(payload[field])
                if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value.lower()):
                    raise LayerViolation(f"CONSENSUS_{field.upper()}_INVALID")
        elif spec.layer == 8:
            changed = bool(payload["changed"])
            if changed and payload["before_root"] == payload["after_root"]:
                raise LayerViolation("OBSERVATION_CHANGE_FLAG_FALSE_EVIDENCE")
            if (not changed) and payload["before_root"] != payload["after_root"]:
                raise LayerViolation("OBSERVATION_CHANGE_FLAG_MISMATCH")
        elif spec.layer == 9:
            if str(payload["claim_state"]) not in {"OBSERVED", "VERIFIED", "FALSIFIED", "REVIEW_REQUIRED"}:
                raise LayerViolation("EVIDENCE_CLAIM_STATE_INVALID")
            if int(payload["receipt_count"]) != 8:
                raise LayerViolation("EVIDENCE_RECEIPT_COUNT_MUST_BE_EIGHT_PRIOR_LAYERS")

    def _expected_input_root(self, layer: int) -> str:
        if layer == 1:
            return self.GENESIS
        prior = self._committed.get(layer - 1)
        if prior is None:
            raise LayerViolation("UPSTREAM_LAYER_NOT_COMMITTED")
        return prior.output_root

    def _expected_prior_receipt_hash(self, layer: int) -> str:
        if layer == 1:
            return self.GENESIS
        prior = self._committed.get(layer - 1)
        if prior is None:
            raise LayerViolation("UPSTREAM_RECEIPT_MISSING")
        return prior.receipt_hash

    def apply(
        self,
        *,
        run_id: str,
        layer: int,
        generation: int,
        payload: Mapping[str, Any],
        processor: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None,
        inject_failure: str | None = None,
    ) -> LayerReceipt:
        if layer not in self.SPECS:
            raise LayerViolation("LAYER_OUT_OF_RANGE")
        if generation <= 0:
            raise LayerViolation("GENERATION_MUST_BE_POSITIVE")
        if self._run_id is not None and run_id != self._run_id:
            raise LayerViolation("RUN_ID_CONFLICT")
        if self._generation and generation < self._generation:
            raise LayerViolation("STALE_PIPELINE_GENERATION")
        spec = self.SPECS[layer]
        self._validate_payload(spec, payload)

        # Idempotent replay for an already committed stage at the same generation.
        existing = self._committed.get(layer)
        payload_root = digest(payload)
        if existing and existing.generation == generation:
            if existing.payload_root != payload_root:
                raise LayerViolation("SAME_GENERATION_PAYLOAD_CONFLICT")
            return existing

        if existing and generation <= existing.generation:
            raise LayerViolation("STALE_LAYER_GENERATION")

        # New upstream generation invalidates the entire downstream suffix.
        if layer in self._committed and generation > self._committed[layer].generation:
            for downstream in range(layer, 10):
                self._committed.pop(downstream, None)
                self._payloads.pop(downstream, None)

        expected_input = self._expected_input_root(layer)
        expected_receipt = self._expected_prior_receipt_hash(layer)

        try:
            if inject_failure:
                raise RuntimeError(inject_failure)
            normalized = dict(processor(payload) if processor else payload)
            self._validate_payload(spec, normalized)
            normalized_root = digest(normalized)
            output_root = digest({
                "run_id": run_id,
                "layer": layer,
                "name": spec.name,
                "generation": generation,
                "input_root": expected_input,
                "payload_root": normalized_root,
            })
            receipt = LayerReceipt.build(
                run_id=run_id,
                spec=spec,
                generation=generation,
                prior_receipt_hash=expected_receipt,
                input_root=expected_input,
                payload_root=normalized_root,
                output_root=output_root,
                status="COMMITTED",
                error=None,
            )
        except Exception as exc:
            failure = LayerReceipt.build(
                run_id=run_id,
                spec=spec,
                generation=generation,
                prior_receipt_hash=expected_receipt,
                input_root=expected_input,
                payload_root=payload_root,
                output_root="",
                status="FAILED",
                error=f"{type(exc).__name__}:{exc}",
            )
            self._failures.append(failure)
            if isinstance(exc, LayerViolation):
                raise
            raise LayerViolation(f"LAYER_{layer}_EXECUTION_FAILED:{type(exc).__name__}:{exc}") from exc

        self._run_id = run_id
        self._generation = max(self._generation, generation)
        self._committed[layer] = receipt
        self._payloads[layer] = normalized

        # Any older downstream suffix is causally invalid once this layer commits.
        for downstream in range(layer + 1, 10):
            stale = self._committed.get(downstream)
            if stale and stale.generation <= generation:
                self._committed.pop(downstream, None)
                self._payloads.pop(downstream, None)
        return receipt

    def reconcile_all(
        self,
        *,
        run_id: str,
        generation: int,
        payloads: Mapping[int, Mapping[str, Any]],
        processors: Mapping[int, Callable[[Mapping[str, Any]], Mapping[str, Any]]] | None = None,
        fault_layer: int | None = None,
        fault_message: str = "injected stage fault",
    ) -> tuple[LayerReceipt, ...]:
        if set(payloads) != set(range(1, 10)):
            raise LayerViolation("ALL_NINE_LAYERS_REQUIRED")
        processors = processors or {}
        receipts: list[LayerReceipt] = []
        for layer in range(1, 10):
            receipt = self.apply(
                run_id=run_id,
                layer=layer,
                generation=generation,
                payload=payloads[layer],
                processor=processors.get(layer),
                inject_failure=fault_message if layer == fault_layer else None,
            )
            receipts.append(receipt)
        self.verify_chain()
        return tuple(receipts)

    def verify_chain(self) -> str:
        prior_output = self.GENESIS
        prior_receipt = self.GENESIS
        if set(self._committed) != set(range(1, 10)):
            raise LayerViolation("PIPELINE_INCOMPLETE")
        for layer in range(1, 10):
            spec = self.SPECS[layer]
            receipt = self._committed[layer]
            if receipt.status != "COMMITTED":
                raise LayerViolation("NON_COMMITTED_RECEIPT_IN_CHAIN")
            if receipt.input_root != prior_output:
                raise LayerViolation(f"LAYER_{layer}_INPUT_CHAIN_BROKEN")
            if receipt.prior_receipt_hash != prior_receipt:
                raise LayerViolation(f"LAYER_{layer}_RECEIPT_CHAIN_BROKEN")
            body = {
                "run_id": receipt.run_id,
                "layer": receipt.layer,
                "name": receipt.name,
                "generation": receipt.generation,
                "prior_receipt_hash": receipt.prior_receipt_hash,
                "input_root": receipt.input_root,
                "payload_root": receipt.payload_root,
                "output_root": receipt.output_root,
                "status": receipt.status,
                "error": receipt.error,
            }
            if digest(body) != receipt.receipt_hash:
                raise LayerViolation(f"LAYER_{layer}_RECEIPT_HASH_MISMATCH")
            prior_output = receipt.output_root
            prior_receipt = receipt.receipt_hash
        return prior_output

    def receipt_bundle(self) -> dict[str, Any]:
        self.verify_chain()
        return {
            "schema": "braink.layer1-9.receipt-bundle.v2",
            "run_id": self._run_id,
            "generation": self._generation,
            "layer_root": self.root,
            "receipt_root": self.receipt_root,
            "receipts": [asdict(self._committed[i]) for i in range(1, 10)],
            "failure_receipts": [asdict(x) for x in self._failures],
        }
