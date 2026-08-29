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
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


class DeterministicFailoverRuntime:
    """Derive service outputs through strict path_a -> path_b -> path_c failover."""

    def __init__(self, root: Path):
        self.root = root.expanduser().resolve()
        self.registry = read_json(
            self.root / "config" / "universal_capability_derivation_registry.json"
        )
        self.components = {
            component["componentId"]: component
            for component in self.registry["components"]
        }
        self.services = {
            service["serviceId"]: service for service in self.registry["services"]
        }
        self.path_order = list(self.registry["selectionPolicy"]["pathOrder"])
        self.runtime_dir = self.root / "runtime_volume" / "deterministic_failover"

    def validate(self) -> List[str]:
        errors: List[str] = []
        if self.path_order != ["path_a", "path_b", "path_c"]:
            errors.append("path_order_must_be_path_a_path_b_path_c")
        if self.registry["selectionPolicy"].get("allowPartialPathMerge") is not False:
            errors.append("partial_path_merge_must_be_false")
        for service_id, service in self.services.items():
            seen_outputs: Set[str] = set()
            for output in service.get("outputs", []):
                output_id = output.get("outputId")
                if not output_id:
                    errors.append(f"{service_id}:missing_output_id")
                    continue
                if output_id in seen_outputs:
                    errors.append(f"{service_id}:duplicate_output:{output_id}")
                seen_outputs.add(output_id)
                declared = [path.get("pathId") for path in output.get("derivationPaths", [])]
                expected = [path_id for path_id in self.path_order if path_id in declared]
                if declared != expected:
                    errors.append(
                        f"{service_id}:{output_id}:paths_not_in_deterministic_order:{declared}"
                    )
                if len(set(declared)) != len(declared):
                    errors.append(f"{service_id}:{output_id}:duplicate_path")
                for path in output.get("derivationPaths", []):
                    if path.get("pathId") not in self.path_order:
                        errors.append(
                            f"{service_id}:{output_id}:undeclared_path:{path.get('pathId')}"
                        )
                    if not path.get("requiredInputs"):
                        errors.append(
                            f"{service_id}:{output_id}:{path.get('pathId')}:missing_inputs"
                        )
        return errors

    def available_inputs(self, available_components: Iterable[str]) -> Set[str]:
        inputs: Set[str] = set()
        for component_id in available_components:
            component = self.components.get(component_id)
            if component:
                inputs.update(component.get("supplies", []))
        return inputs

    def derive_output(self, output: Dict[str, Any], available_inputs: Set[str]) -> Dict[str, Any]:
        evaluated: List[Dict[str, Any]] = []
        selected: Optional[Dict[str, Any]] = None
        paths_by_id = {
            path["pathId"]: path for path in output.get("derivationPaths", [])
        }
        for path_id in self.path_order:
            path = paths_by_id.get(path_id)
            if path is None:
                continue
            required = set(path["requiredInputs"])
            missing = sorted(required - available_inputs)
            evaluation = {
                "path_id": path_id,
                "quality": path["quality"],
                "required_inputs": sorted(required),
                "missing_inputs": missing,
                "complete": not missing,
            }
            evaluated.append(evaluation)
            if not missing:
                selected = evaluation
                break

        mandatory = bool(output.get("mandatory"))
        if selected:
            state_map = {
                "path_a": "FULLY_DERIVED",
                "path_b": "SUBSTITUTED",
                "path_c": "DEGRADED_DERIVATION",
            }
            output_state = state_map[selected["path_id"]]
        else:
            output_state = "BOUNDED_STOP" if mandatory else "DEFERRED_INPUT"

        return {
            "output_id": output["outputId"],
            "mandatory": mandatory,
            "evaluated_paths": evaluated,
            "selected_path": selected["path_id"] if selected else None,
            "selected_quality": selected["quality"] if selected else None,
            "output_state": output_state,
            "derived": selected is not None,
        }

    def execute(
        self,
        service_id: str,
        available_components: Iterable[str],
    ) -> Dict[str, Any]:
        if service_id not in self.services:
            return {
                "service_id": service_id,
                "service_state": "CONTEXT_RESOLUTION_REQUIRED",
                "global_stop": False,
                "reason": "unknown_service",
            }

        component_ids = sorted(set(available_components))
        available_inputs = self.available_inputs(component_ids)
        service = self.services[service_id]
        outputs = [
            self.derive_output(output, available_inputs)
            for output in service.get("outputs", [])
        ]

        mandatory = [output for output in outputs if output["mandatory"]]
        optional = [output for output in outputs if not output["mandatory"]]
        mandatory_blocked = [output for output in mandatory if not output["derived"]]
        selected_paths = [output["selected_path"] for output in mandatory if output["selected_path"]]

        if mandatory_blocked:
            service_state = "BOUNDED_STOP"
        elif "path_c" in selected_paths:
            service_state = "DEGRADED_DERIVATION"
        elif "path_b" in selected_paths:
            service_state = "SUBSTITUTED"
        elif optional and any(not output["derived"] for output in optional):
            service_state = "DEFERRED_INPUT"
        else:
            service_state = "FULLY_DERIVED"

        timestamp = time.time()
        receipt = {
            "version": self.registry["version"],
            "service_id": service_id,
            "available_components": component_ids,
            "available_inputs": sorted(available_inputs),
            "outputs": outputs,
            "service_state": service_state,
            "impact_radius": [output["output_id"] for output in outputs if not output["derived"]],
            "preserved_outputs": [output["output_id"] for output in outputs if output["derived"]],
            "global_stop": False,
            "timestamp": timestamp,
        }
        receipt_id = canonical_hash(receipt)
        receipt["receipt_id"] = f"receipt://deterministic-failover/{receipt_id}"
        write_json(self.runtime_dir / "receipts" / f"{receipt_id}.json", receipt)

        service_to_output = (
            read_json(self.runtime_dir / "service_to_output.json")
            if (self.runtime_dir / "service_to_output.json").exists()
            else {}
        )
        output_to_service = (
            read_json(self.runtime_dir / "output_to_service.json")
            if (self.runtime_dir / "output_to_service.json").exists()
            else {}
        )
        service_to_output[service_id] = sorted(output["output_id"] for output in outputs)
        for output in outputs:
            output_to_service.setdefault(output["output_id"], [])
            if service_id not in output_to_service[output["output_id"]]:
                output_to_service[output["output_id"]].append(service_id)
                output_to_service[output["output_id"]].sort()
        write_json(self.runtime_dir / "service_to_output.json", service_to_output)
        write_json(self.runtime_dir / "output_to_service.json", output_to_service)
        receipt["bilateral_readback"] = all(
            output["output_id"] in service_to_output.get(service_id, [])
            and service_id in output_to_service.get(output["output_id"], [])
            for output in outputs
        )
        write_json(self.runtime_dir / "current_execution.json", receipt)
        return receipt


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--service", default="service://universal/example")
    parser.add_argument("--component", action="append", default=[])
    parser.add_argument("--emit-receipt", action="store_true")
    args = parser.parse_args(argv)

    runtime = DeterministicFailoverRuntime(Path(args.root))
    errors = runtime.validate()
    result = runtime.execute(args.service, args.component)
    payload = {"registry_valid": not errors, "errors": errors, "result": result}
    if args.emit_receipt:
        write_json(runtime.root / "evidence" / "deterministic_failover_receipt.json", payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if not errors and result.get("bilateral_readback") else 1


if __name__ == "__main__":
    raise SystemExit(main())
