from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Callable, Mapping, Optional
import hashlib
import json
import time

from enterprise.foundry_closure_r23 import DurableStore, ResearchPromotionGate, TransitionReceipt
from enterprise.governance.authorship_guard import stamp


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def root(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


@dataclass(frozen=True)
class DependencyResolution:
    capability: str
    state: str
    resource_id: Optional[str]
    provider: Optional[str]
    external_ref: Optional[str]
    reason: str

    @property
    def resolution_root(self) -> str:
        return root(asdict(self))


class R23DependencyResolver:
    """Bind R23 closure operations to already-resident service resources.

    This class deliberately does not create provider capability. It resolves an
    observed R25 service resource, checks the declared capability contract, and
    returns a typed hole when the required actuator is not resident.
    """

    def __init__(self, store: DurableStore, service_fabric: Any):
        self.store = store
        self.service_fabric = service_fabric

    def resolve(self, capability: str, service: str) -> DependencyResolution:
        resource = self.service_fabric.resolve_resource(service)
        if not resource:
            return DependencyResolution(
                capability, "TYPED_HOLE", None, None, None,
                f"resident service resource absent: {service}",
            )
        return DependencyResolution(
            capability,
            "RESIDENT_RESOURCE",
            str(resource.get("resource_id")),
            str(resource.get("provider")),
            str(resource.get("external_ref")),
            "resolved through R25 external_resources",
        )

    def bind_mail_control_plane(self, business_id: str, service: str = "customer_services_mail") -> Mapping[str, Any]:
        resolution = self.resolve("mail.control_plane", service)
        if resolution.state != "RESIDENT_RESOURCE":
            return self._record_resolution("MAIL", "BIND_CONTROL_PLANE", business_id, resolution)
        instance = self.service_fabric.create_service_instance(business_id, service)
        status = "EXECUTED" if instance.get("state") == "ACTIVE" else instance.get("state", "HELD_RESOURCE_HOLE")
        effect = {
            "resolution": asdict(resolution),
            "service_instance": instance,
            "claim_boundary": "GMAIL_CONTROL_PLANE_BOUND_NOT_SMTP_DELIVERY_PROVEN",
        }
        return asdict(self.store.record(TransitionReceipt("MAIL", "BIND_CONTROL_PLANE", business_id, status, effect, time.time_ns())))

    def resolve_publication_actuator(self, service: str = "public_http_origin") -> DependencyResolution:
        return self.resolve("domain.public_activation", service)

    def _record_resolution(self, subsystem: str, operation: str, subject: str, resolution: DependencyResolution) -> Mapping[str, Any]:
        receipt = self.store.record(TransitionReceipt(
            subsystem,
            operation,
            subject,
            resolution.state,
            {"resolution": asdict(resolution), "resolution_root": resolution.resolution_root},
            time.time_ns(),
        ))
        return asdict(receipt)


class ResearchProvenanceRuntime:
    """R23 research promotion qualifier using evidence already supplied to the gate."""

    def __init__(self, store: DurableStore):
        self.store = store
        self.base_gate = ResearchPromotionGate(store)

    def evaluate(
        self,
        research_id: str,
        claims: list[Mapping[str, Any]],
        sources: list[Mapping[str, Any]],
        replays: list[Mapping[str, Any]],
        independent_verifier: Optional[str],
    ) -> TransitionReceipt:
        normalized_sources = []
        for source in sources:
            item = dict(source)
            evidence = {
                "source": item.get("source") or item.get("uri") or item.get("id"),
                "content_root": item.get("content_root") or item.get("sha256"),
                "observed": bool(item.get("observed", True)),
            }
            evidence["provenance_root"] = root(evidence)
            normalized_sources.append(evidence)

        replay_passes = [r for r in replays if r.get("status") == "PASS"]
        score_components = {
            "source_identity": bool(normalized_sources) and all(s["source"] for s in normalized_sources),
            "content_roots": bool(normalized_sources) and all(s["content_root"] for s in normalized_sources),
            "observed_sources": bool(normalized_sources) and all(s["observed"] for s in normalized_sources),
            "reproducible": bool(replays) and len(replay_passes) == len(replays),
            "independent_verifier": bool(independent_verifier),
        }
        score = sum(1 for value in score_components.values() if value) / len(score_components)
        base = self.base_gate.evaluate(research_id, claims, normalized_sources, replays, independent_verifier)
        state = "PROMOTED_PROVENANCE_QUALIFIED" if base.effect["state"] == "PROMOTED" and score == 1.0 else "REVIEW_REQUIRED"
        effect = {
            "base_gate_receipt_root": base.receipt_root,
            "state": state,
            "provenance_score": score,
            "score_components": score_components,
            "source_roots": [s["provenance_root"] for s in normalized_sources],
        }
        effect["provenance_evidence_root"] = root(effect)
        return self.store.record(TransitionReceipt("RESEARCH", "PROVENANCE_PROMOTION", research_id, "EXECUTED", effect, time.time_ns()))


def authorship_receipt(service_id: str, deployment_id: str, content_root: str, created_utc: str, predecessor_id: Optional[str] = None) -> Mapping[str, Any]:
    """Stamp a dependency deployment without creating a parallel authorship model."""
    return stamp(
        service_id=service_id,
        deployment_id=deployment_id,
        repository="aboudykeddeh276-stack/BRAINK",
        content_root=content_root,
        created_utc=created_utc,
        predecessor_id=predecessor_id,
    )
