#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set


def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def canonical_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class HypervisorProviderResolver:
    """Resolve workloads onto capability providers without coupling control-plane ignition to any host."""

    def __init__(self, root: Path):
        self.root = root.expanduser().resolve()
        self.registry = read_json(self.root / "config" / "hypervisor_provider_registry.json")
        self.providers = {p["providerId"]: p for p in self.registry["providers"]}
        self.workloads = {w["workloadId"]: w for w in self.registry["workloads"]}
        self.runtime_dir = self.root / "runtime_volume" / "hypervisor_provider_resolution"

    def validate(self) -> List[str]:
        errors: List[str] = []
        for provider_id, provider in self.providers.items():
            for field in ("class", "runner", "capabilities", "priority", "availability", "evidenceClass"):
                if field not in provider or provider[field] in (None, "", []):
                    errors.append(f"{provider_id}:missing:{field}")
        for workload_id, workload in self.workloads.items():
            for field in ("requiredCapabilities", "preferredProviders", "substitutionPolicy", "unavailablePolicy"):
                if field not in workload or workload[field] in (None, "", []):
                    errors.append(f"{workload_id}:missing:{field}")
            for provider_id in workload.get("preferredProviders", []):
                if provider_id not in self.providers:
                    errors.append(f"{workload_id}:unknown_provider:{provider_id}")
        return errors

    @staticmethod
    def _availability_state(provider: Dict[str, Any], observed_available: Set[str]) -> str:
        provider_id = provider["providerId"]
        if provider_id in observed_available:
            return "AVAILABLE"
        if provider["availability"] == "ASSUMED_BY_WORKFLOW_DISPATCH":
            return "AVAILABLE"
        return "UNAVAILABLE"

    def resolve(self, workload_id: str, observed_available: Iterable[str] = ()) -> Dict[str, Any]:
        if workload_id not in self.workloads:
            return {
                "promotion_state": "CONTEXT_RESOLUTION_REQUIRED",
                "workload_id": workload_id,
                "global_stop": False,
                "reason": "unknown_workload",
            }

        available = set(observed_available)
        workload = self.workloads[workload_id]
        required = set(workload["requiredCapabilities"])
        assessments: List[Dict[str, Any]] = []
        eligible: List[Dict[str, Any]] = []

        preference_rank = {pid: index for index, pid in enumerate(workload["preferredProviders"])}
        for provider_id in workload["preferredProviders"]:
            provider = self.providers[provider_id]
            capabilities = set(provider["capabilities"])
            missing = sorted(required - capabilities)
            availability_state = self._availability_state(provider, available)
            assessment = {
                "provider_id": provider_id,
                "availability_state": availability_state,
                "required_capabilities": sorted(required),
                "provided_capabilities": sorted(capabilities),
                "missing_capabilities": missing,
                "eligible": availability_state == "AVAILABLE" and not missing,
                "evidence_class": provider["evidenceClass"],
            }
            assessments.append(assessment)
            if assessment["eligible"]:
                eligible.append(provider)

        eligible.sort(key=lambda p: (preference_rank.get(p["providerId"], 999), p["priority"]))
        timestamp = time.time()
        base = {
            "version": self.registry["version"],
            "workload_id": workload_id,
            "required_capabilities": sorted(required),
            "provider_assessments": assessments,
            "timestamp": timestamp,
            "global_stop": False,
        }

        if eligible:
            selected = eligible[0]
            receipt = {
                **base,
                "promotion_state": "PROVIDER_SELECTED",
                "selected_provider": selected["providerId"],
                "selected_provider_class": selected["class"],
                "selected_runner": selected["runner"],
                "execution_state": "ROUTED",
                "apple_specific": bool(workload.get("appleSpecific")),
                "substitution_applied": selected["providerId"] != workload["preferredProviders"][0],
            }
        else:
            packet_seed = {
                "workload_id": workload_id,
                "required_capabilities": sorted(required),
                "assessments": assessments,
            }
            packet_id = canonical_hash(packet_seed)
            packet = {
                "work_item_id": f"work://provider-reentry/{packet_id}",
                "blocked_capability": workload_id,
                "blocked_domain": "provider-resolution",
                "criticality": "EXTERNAL_GATE" if workload.get("appleSpecific") else "CORE_DEGRADED",
                "root_cause": "no currently observed provider satisfies all required capabilities",
                "impact_radius": [workload_id],
                "unaffected_domains": [wid for wid in sorted(self.workloads) if wid != workload_id],
                "continuation_mode": workload["unavailablePolicy"],
                "fallback_adapter": "adapter.hypervisor-provider-retry",
                "reentry_conditions": ["provider availability receipt", "capability-set readback"],
                "promotion_evidence": ["provider execution receipt", "workload result receipt"],
                "global_stop": False,
            }
            write_json(self.root / "runtime_volume" / "workplans" / "provider_reentry" / f"{packet_id}.json", packet)
            receipt = {
                **base,
                "promotion_state": "DEFERRED",
                "selected_provider": None,
                "selected_runner": None,
                "execution_state": "DEFERRED",
                "continuation_packet": packet,
                "apple_specific": bool(workload.get("appleSpecific")),
            }

        receipt_id = canonical_hash(receipt)
        receipt["receipt_id"] = f"receipt://hypervisor-provider-resolution/{receipt_id}"
        write_json(self.runtime_dir / "receipts" / f"{receipt_id}.json", receipt)

        forward = read_json(self.runtime_dir / "workload_to_provider.json") if (self.runtime_dir / "workload_to_provider.json").exists() else {}
        reverse = read_json(self.runtime_dir / "provider_to_workload.json") if (self.runtime_dir / "provider_to_workload.json").exists() else {}
        selected_provider = receipt.get("selected_provider")
        forward.setdefault(workload_id, [])
        if selected_provider and selected_provider not in forward[workload_id]:
            forward[workload_id].append(selected_provider)
            reverse.setdefault(selected_provider, [])
            if workload_id not in reverse[selected_provider]:
                reverse[selected_provider].append(workload_id)
        write_json(self.runtime_dir / "workload_to_provider.json", forward)
        write_json(self.runtime_dir / "provider_to_workload.json", reverse)
        receipt["bilateral_readback"] = (
            selected_provider is None
            or (selected_provider in forward.get(workload_id, []) and workload_id in reverse.get(selected_provider, []))
        )
        write_json(self.runtime_dir / "current_resolution.json", receipt)
        return receipt


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--workload", default="workload://host-acceptance/portable")
    parser.add_argument("--available", action="append", default=[])
    parser.add_argument("--emit-receipt", action="store_true")
    args = parser.parse_args(argv)
    runtime = HypervisorProviderResolver(Path(args.root))
    errors = runtime.validate()
    result = runtime.resolve(args.workload, args.available)
    payload = {"registry_valid": not errors, "errors": errors, "result": result}
    if args.emit_receipt:
        write_json(runtime.root / "evidence" / "hypervisor_provider_resolution_receipt.json", payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if not errors and result.get("bilateral_readback") else 1


if __name__ == "__main__":
    raise SystemExit(main())
