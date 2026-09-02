from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Iterable, Mapping
import hashlib
import json
import time


def root(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Component:
    name: str
    version: str
    supplier: str
    source_ref: str
    integrity_root: str
    license_id: str = "UNKNOWN"


@dataclass(frozen=True)
class BuildProvenance:
    build_id: str
    source_root: str
    builder_id: str
    workflow_ref: str
    input_roots: tuple[str, ...]
    output_roots: tuple[str, ...]
    produced_at_ns: int

    @property
    def provenance_root(self) -> str:
        return root(asdict(self))


class SupplyChainLedger:
    def __init__(self):
        self.components: list[Component] = []
        self.builds: list[BuildProvenance] = []

    def add_component(self, component: Component) -> None:
        if not component.integrity_root:
            raise RuntimeError("COMPONENT_INTEGRITY_REQUIRED")
        self.components.append(component)

    def add_build(self, provenance: BuildProvenance) -> None:
        if not provenance.source_root or not provenance.output_roots:
            raise RuntimeError("BUILD_PROVENANCE_INCOMPLETE")
        self.builds.append(provenance)

    def sbom(self, product_name: str, product_version: str) -> Mapping[str, Any]:
        doc = {
            "schema": "braink.sbom/v1",
            "product": {"name": product_name, "version": product_version},
            "components": [asdict(c) for c in sorted(self.components, key=lambda c: (c.name, c.version))],
            "generated_at_ns": time.time_ns(),
        }
        return {**doc, "sbom_root": root(doc)}

    def provenance_snapshot(self) -> Mapping[str, Any]:
        builds = [asdict(b) | {"provenance_root": b.provenance_root} for b in self.builds]
        doc = {"schema": "braink.build-provenance/v1", "builds": builds}
        return {**doc, "ledger_root": root(doc)}
